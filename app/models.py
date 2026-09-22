from datetime import date, datetime, time as dt_time
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Catalog(Base):
    """Leistungskatalog (seit 1.0.14). Genau ein Katalog trägt is_import_catalog=True
    ('Fertigkatalog') -- Importe landen dort standardmäßig, sind aber beim
    Import auf einen anderen Katalog umstellbar. Weitere Kataloge können
    manuell angelegt werden. Kein echtes Löschen vorgesehen -- nur Archivieren
    (archived=True), damit bereits in Angeboten verwendete Leistungen nicht
    verwaist."""

    __tablename__ = "catalogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_import_catalog: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    services: Mapped[list["Service"]] = relationship(back_populates="catalog")
    calculation_settings: Mapped["CalculationSettings | None"] = relationship(back_populates="catalog")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    services: Mapped[list["Service"]] = relationship(back_populates="import_batch")


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("source_type", "external_id", name="uq_service_source_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))
    catalog_id: Mapped[int | None] = mapped_column(ForeignKey("catalogs.id"), nullable=True, index=True)
    service_type: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # 'lohnarbeit' | 'fremdleistung' | 'material' -- für Auswertungen, seit 1.0.25

    source_type: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(100), index=True)
    title_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_text: Mapped[str] = mapped_column(Text)
    long_text: Mapped[str] = mapped_column(Text, default="")
    rtf_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(50))
    site_time_raw: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    workshop_time_raw: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    time_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    activity_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="services")
    catalog: Mapped["Catalog | None"] = relationship(back_populates="services")
    materials: Mapped[list["ServiceMaterial"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )
    calculation: Mapped["ServiceCalculation | None"] = relationship(
        back_populates="service", cascade="all, delete-orphan", uselist=False
    )
    material_overrides: Mapped[list["MaterialCalculationOverride"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )


class MaterialGroup(Base):
    """Materialkatalog (seit 1.0.30) -- eigenständiges Container-Konzept,
    genau nach dem Vorbild von Catalog für Leistungen. Bewusst NICHT
    "MaterialCatalog" genannt (auch wenn die Oberfläche das Wort
    "Materialkataloge" verwendet): der Name wäre mit dem bereits bestehenden
    Schema MaterialCatalogOut kollidiert, das ein einzelnes Material im
    (bisher katalogfreien) Materialkatalog von 1.0.25 darstellt.

    Genau eine Gruppe trägt is_import_catalog=True ('Fertigkatalog') --
    importierte und neu erzeugte Materialien landen dort standardmäßig.
    Kein echtes Löschen -- nur Archivieren."""

    __tablename__ = "material_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_import_catalog: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    materials: Mapped[list["Material"]] = relationship(back_populates="catalog")


class Material(Base):
    """Materialkatalog (seit 1.0.25): ein Material, viele Leistungen können
    darauf verweisen -- vorher hatte jede Leistung ihre eigene, unabhängige
    Materialzeile, auch wenn es fachlich dasselbe Material war.

    Absichtlich als eigenständige, nicht an Service gebundene Stammdaten-
    Tabelle angelegt (nicht z.B. in service.py) -- soll sich künftig auch mit
    Zeiterfassung/Reparatur-&Wartungsmodul verknüpfen lassen, nicht nur mit
    Leistungen."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(50))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    price_basis: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))
    source: Mapped[str] = mapped_column(String(20), default="imported", index=True)  # 'imported' | 'manual'
    catalog_id: Mapped[int | None] = mapped_column(ForeignKey("material_groups.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    service_materials: Mapped[list["ServiceMaterial"]] = relationship(back_populates="material")
    catalog: Mapped["MaterialGroup | None"] = relationship(back_populates="materials")


class ServiceMaterial(Base):
    __tablename__ = "service_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True, index=True)

    name: Mapped[str] = mapped_column(Text)
    article_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(50))
    waste_raw: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    price_basis: Mapped[Decimal] = mapped_column(Numeric(18, 6))

    material: Mapped["Material | None"] = relationship(back_populates="service_materials")
    service: Mapped[Service] = relationship(back_populates="materials")


class CalculationSettings(Base):
    """Kalkulationsvorgaben. id=1 ist der globale Fallback ohne Katalogbezug
    (seit Prototype 0.2). Seit 1.0.14 kann zusätzlich je Katalog ein eigener
    Datensatz existieren (catalog_id gesetzt) -- fehlt er, gilt weiterhin der
    globale Datensatz. Siehe get_settings_for_catalog() in calculation.py.

    Bewusst OHNE id-Default (anders als die übrigen Singleton-Einstellungen
    in diesem Modul, z. B. GeneralSettings): get_or_create_settings() setzt
    id=1 für den globalen Datensatz weiterhin explizit, aber jeder neue,
    katalogeigene Datensatz muss eine echte, automatisch vergebene ID
    bekommen -- mit einem Default von 1 würden mehrere neu angelegte
    Datensätze sonst um dieselbe ID konkurrieren."""

    __tablename__ = "calculation_settings"
    __table_args__ = (UniqueConstraint("catalog_id", name="uq_calculation_settings_catalog"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int | None] = mapped_column(ForeignKey("catalogs.id"), nullable=True)
    labor_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("82.00"))
    material_markup_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    overhead_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    risk_profit_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    use_source_time_as_minutes: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    catalog: Mapped["Catalog | None"] = relationship(back_populates="calculation_settings")


class ServiceCalculation(Base):
    """DACHKONZEPTE-eigene Kalkulation; getrennt von den importierten Originaldaten."""

    __tablename__ = "service_calculations"
    __table_args__ = (UniqueConstraint("service_id", name="uq_service_calculation_service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)

    site_time_minutes: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    workshop_time_minutes: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    labor_rate_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    material_markup_pct_override: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    equipment_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    subcontractor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    other_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    overhead_pct_override: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    risk_profit_pct_override: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    manual_sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    service: Mapped[Service] = relationship(back_populates="calculation")


class MaterialCalculationOverride(Base):
    """Eigene Materialwerte; logischer Schlüssel bleibt auch bei erneutem XML-Import stabil."""

    __tablename__ = "material_calculation_overrides"
    __table_args__ = (
        UniqueConstraint(
            "service_id", "article_number_key", "material_name_key",
            name="uq_material_override_logical_key"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    article_number_key: Mapped[str] = mapped_column(String(100), default="")
    material_name_key: Mapped[str] = mapped_column(Text)

    quantity_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    waste_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    purchase_price_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_basis_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    service: Mapped[Service] = relationship(back_populates="material_overrides")


class Customer(Base):
    """`name` ist seit dem Adressimport aus dem Altsystem (siehe CLAUDE.md) ein rein
    serverseitig abgeleitetes Feld -- zusammengesetzt aus salutation/title/first_name/
    last_name (siehe `app.crm.compose_customer_name()`), nicht mehr direkt beschreibbar.
    last_name ist das eigentliche Pflichtfeld (auch für Firmenkunden: dort trägt es den
    Firmennamen, salutation/title/first_name bleiben leer)."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("legacy_address_number", name="uq_customer_legacy_address_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    salutation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255))
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str] = mapped_column(String(120), default="Deutschland", server_default="Deutschland")
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Zweite E-Mail-Adresse (Adressimport, seit CLAUDE.md "Adressimport aus dem
    # Altsystem") -- bewusst rein informativ, fließt NICHT in get_*_recipient_email()
    # (app/projects.py, orders.py, invoices.py, reminders.py) ein: die dortigen
    # Versandfunktionen kennen strukturell nur einen einzigen Empfänger (to_email: str,
    # ein SMTP-/Graph-Empfänger je Sendevorgang) -- echte Mehrfachversand-Unterstützung
    # wäre ein eigener, größerer Umbau, kein Nebeneffekt des Adressimports.
    email_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Adressnummer aus dem Altsystem (Spalte "Adresse" im Quellexport) -- dient beim
    # erneuten Import derselben Datei der Wiedererkennung bereits übernommener Zeilen.
    # Bewusst direkt auf Customer/Supplier statt über CustomerProfile geführt: Supplier
    # hat kein Profil-Äquivalent, für dasselbe Konzept sollen beide denselben Ort nutzen.
    legacy_address_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["CustomerProfile | None"] = relationship(
        back_populates="customer", cascade="all, delete-orphan", uselist=False
    )
    properties: Mapped[list["Property"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="customer")
    inquiries: Mapped[list["Inquiry"]] = relationship(back_populates="customer")
    extra_infos: Mapped[list["CustomerExtraInfo"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", order_by="CustomerExtraInfo.id"
    )
    documents: Mapped[list["CustomerDocument"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", order_by="CustomerDocument.uploaded_at.desc()"
    )


    @property
    def customer_number(self) -> str | None:
        return self.profile.customer_number if self.profile else None

    @property
    def category(self) -> str:
        return self.profile.category if self.profile else "Privatkunde"

    @property
    def default_payment_term_id(self) -> int | None:
        return self.profile.default_payment_term_id if self.profile else None


class CustomerProfile(Base):
    """Erweiterbare CRM-Stammdaten ohne invasive Änderungen an bestehenden Kundentabellen."""

    __tablename__ = "customer_profiles"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_customer_profile_customer"),
        UniqueConstraint("customer_number", name="uq_customer_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    customer_number: Mapped[str] = mapped_column(String(50), index=True)
    category: Mapped[str] = mapped_column(String(80), default="Privatkunde", index=True)
    default_payment_term_id: Mapped[int | None] = mapped_column(ForeignKey("payment_terms.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer: Mapped[Customer] = relationship(back_populates="profile")
    default_payment_term: Mapped["PaymentTerm | None"] = relationship()


class TaxKey(Base):
    """Steuerschlüssel (seit 1.0.44) -- steuert sowohl den auf Angebot/
    Auftrag/Rechnung angezeigten Hinweistext als auch den tatsächlich
    verwendeten vat_rate. Bewusst als eigenständige Auswahl UND nicht als
    Ersatz für das vat_rate-Feld selbst: vat_rate bleibt das Feld, das die
    komplette bestehende Berechnungslogik (Angebot/Auftrag/Rechnung) nutzt --
    ein Steuerschlüssel setzt vat_rate beim Auswählen neu, die eigentliche
    Berechnung merkt vom Steuerschlüssel selbst nichts. Damit ändert sich an
    der bereits umfassend getesteten Kernberechnung nichts, nur eine neue,
    vorgelagerte Auswahl kommt hinzu.

    'Privat'/'Gewerbe' haben in der Praxis denselben Satz wie der
    Normalfall (kein steuerlicher Sondertatbestand), §13b (Bauleistungen,
    Steuerschuldnerschaft des Leistungsempfängers) und Solar (§12 Abs. 3
    UStG, Nullsteuersatz) senken vat_rate auf 0."""

    __tablename__ = "tax_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("19.00"))
    notice_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaymentTerm(Base):
    """Zahlungsbedingung (seit 1.0.37) -- eigenständiges, kleines Verwaltungs-
    Objekt statt Teil der generischen Auswahllisten (SettingOption), da eine
    Zahlungsbedingung zusätzlich zu Name/Sortierung eine strukturierte
    Fälligkeitsfrist in Tagen braucht, die alle anderen Auswahllisten nicht
    haben -- die generische Tabelle würde damit für alle anderen Gruppen ein
    ungenutztes Feld mitschleppen.

    Genau eine Bedingung trägt is_default=True und wird als Vorbelegung
    verwendet, wenn ein Kunde keine eigene hinterlegt hat. days ist die
    Grundlage für die automatische Fälligkeitsberechnung von Rechnungen
    (invoice_date + days = due_date) und später für das Mahnwesen.

    skonto_percent/skonto_days (seit 1.0.41) bilden echtes Skonto ab: bei
    Zahlung innerhalb von skonto_days Tagen wird skonto_percent % Abzug
    gewährt. Beide zusammen optional -- None/None heißt "kein Skonto".

    text_template (seit 1.0.42) überschreibt den automatisch erzeugten
    Fälligkeits-/Skontosatz mit einem frei formulierten Text. Platzhalter
    {faelligkeitsdatum}/{skontodatum}/{skontoprozent}/{skontobetrag} werden
    beim Erzeugen der Rechnung durch die tatsächlichen Werte ersetzt. Leer =
    weiterhin der Standardsatz aus format_payment_terms_sentence()."""

    __tablename__ = "payment_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    days: Mapped[int] = mapped_column(default=14)
    skonto_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    skonto_days: Mapped[int | None] = mapped_column(nullable=True)
    text_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerExtraInfo(Base):
    """Flexible zusätzliche Kontaktdaten und CRM-Informationen zum Kunden."""

    __tablename__ = "customer_extra_infos"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    info_type: Mapped[str] = mapped_column(String(30), index=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    value: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[Customer] = relationship(back_populates="extra_infos")


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Seit dem Adressimport aus dem Altsystem (siehe CLAUDE.md) -- nullable ohne
    # Default, da die weit überwiegende Zahl bestehender Objekte davon unberührt bleibt.
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Seit "Rechtekonzept" (siehe CLAUDE.md): ein Monteur soll den Zugang zu einem Objekt und
    # den Ansprechpartner vor Ort ausschließlich über den Einsatzbericht erfahren, nicht über
    # die Kundenakte -- bisher stand dafür nichts Strukturiertes zur Verfügung, nur das oben
    # bereits bestehende, unspezifische notes-Feld. access_notes ist bewusst ein eigenes Feld
    # (nicht notes selbst umgewidmet, um bestehende, dort bereits erfasste Freitexte nicht
    # umzudeuten). site_contact_* ist bewusst NICHT Customer.contact_person -- der
    # Hauptansprechpartner des Kunden ist häufig nicht dieselbe Person, die am konkreten Objekt
    # vor Ort ist (z. B. Hausverwaltung vs. Mieter/Hausmeister).
    access_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    site_contact_phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Seit "Objekte: Hauptadressen kennzeichnen und ausblenden" (siehe CLAUDE.md) -- wird
    # ausschließlich dort gesetzt, wo die Hauptadresse automatisch entsteht
    # (routers/customers.py::create_customer()/update_customer(),
    # address_import.py::_create_customer_from_row()), nie über das normale Objektformular.
    is_primary_address: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[Customer] = relationship(back_populates="properties")
    projects: Mapped[list["Project"]] = relationship(back_populates="property")
    inquiries: Mapped[list["Inquiry"]] = relationship(back_populates="property")
    # Dachflächen (seit 1.2.14) -- anders als projects/inquiries bewusst MIT cascade: Property
    # wird zwar aktuell nirgends im Code gelöscht, aber ein before_delete-Event auf RoofArea
    # (registriert in app/roof_areas.py) räumt beim Löschen -- auch kaskadiert über dieses
    # cascade="all, delete-orphan" -- automatisch die zugehörige Skizzendatei von der Festplatte
    # mit auf. Ein Bulk-DELETE ohne ORM-Instanzen würde dieses Event umgehen (kommt aktuell
    # nirgends vor).
    roof_areas: Mapped[list["RoofArea"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", order_by="RoofArea.name"
    )
    # Objektgebundene Dateien (seit "Dateiablage je Objekt", siehe CLAUDE.md) -- eigene Ablage
    # NEBEN den bereits bestehenden ProjectDocument/CustomerDocument, siehe PropertyDocument
    # unten für die Begründung, warum es keine dritte, polymorphe Tabelle gibt.
    documents: Mapped[list["PropertyDocument"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", order_by="PropertyDocument.uploaded_at.desc()"
    )


class Inquiry(Base):
    """Vertriebsanfrage vor der eigentlichen Projektanlage."""

    __tablename__ = "inquiries"
    __table_args__ = (UniqueConstraint("inquiry_number", name="uq_inquiry_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_number: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True, unique=True)

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="neu", index=True)
    priority: Mapped[str] = mapped_column(String(30), default="normal", index=True)
    source: Mapped[str] = mapped_column(String(80), default="sonstiges", index=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer: Mapped[Customer] = relationship(back_populates="inquiries")
    property: Mapped[Property | None] = relationship(back_populates="inquiries")
    project: Mapped["Project | None"] = relationship(back_populates="source_inquiry", foreign_keys=[project_id])


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("project_number", name="uq_project_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_number: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="anfrage", index=True)
    # Kanban-Spalte der Projektliste (seit 1.3.70) -- eine von `status` oben VOLLSTÄNDIG
    # unabhängige zweite Achse, siehe ProjectPipelineColumn-Klassendocstring für die volle
    # Begründung. `status` bleibt die einzige Quelle für Automatik/Kennzahlen (Beauftragung,
    # Duplizieren, Dashboard-Filter usw.) -- keine Funktion dieses Projekts darf
    # `pipeline_column_id` lesen, um daraus `status` abzuleiten, oder umgekehrt. Jede der vier
    # Project(...)-Konstruktionsstellen (app/projects.py::duplicate_project(),
    # app/quick_service_orders.py, app/routers/inquiries.py::convert_inquiry(),
    # app/routers/projects.py::create_project()) setzt sie explizit auf
    # project_pipeline_columns.default_pipeline_column_id(db) -- ein Projekt ohne Spalte würde
    # im künftigen Kanban unsichtbar bleiben, deshalb NOT NULL statt eines optionalen Felds.
    pipeline_column_id: Mapped[int] = mapped_column(ForeignKey("project_pipeline_columns.id"), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Mustervorgang (seit 1.0.92) -- ein als Vorlage markiertes Projekt bleibt
    # technisch ein normales Projekt (gleiche Tabelle, gleiche Beziehungen),
    # taucht aber nicht in der normalen Projektliste auf, sondern in einer
    # eigenen Vorlagen-Übersicht. Siehe duplicate_project() in projects.py.
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    # Archivieren (seit 1.0.94) -- rein informatives Ausblenden aus der
    # Standardansicht, jederzeit umkehrbar, betrifft weder Daten noch
    # Beziehungen. Gilt für Mustervorgänge wie für normale Projekte
    # gleichermaßen. Echtes Löschen ist zusätzlich möglich, aber nur wenn
    # noch kein Auftrag aus dem Projekt entstanden ist -- siehe
    # delete_project() in projects.py für die Begründung.
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[Customer] = relationship(back_populates="projects")
    property: Mapped[Property | None] = relationship(back_populates="projects")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="Order.id")
    source_inquiry: Mapped["Inquiry | None"] = relationship(back_populates="project", foreign_keys="Inquiry.project_id", uselist=False)
    documents: Mapped[list["ProjectDocument"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectDocument.uploaded_at.desc()"
    )
    profile: Mapped["ProjectProfile | None"] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    pipeline_column: Mapped["ProjectPipelineColumn"] = relationship()


class ProjectPipelineColumn(Base):
    """Konfigurierbare Kanban-Spalte der Projektliste (seit 1.3.70) -- bewusst ein ZWEITES,
    von Project.status vollständig unabhängiges Feld, kein Ersatz dafür.

    Project.status ist heute nicht durchgängig eine freie Anwenderentscheidung: er wird an
    mehreren Stellen automatisch überschrieben (Beauftragung -> "beauftragt", Duplizieren/
    Mustervorgang -> "anfrage", Anfrage-Umwandlung -> "angebot") UND von Kennzahlen gelesen
    (Dashboard-KPI "Aktive Projekte", Widget "Laufende Projekte" -- beide werten feste
    status-Wortlaute aus). Eine frei per Ziehen sortierbare Kanban-Spalte hätte, wäre sie
    dasselbe Feld wie bei TaskColumn/Task.status (siehe dort -- dort IST die Spalte der
    Status, kein separates Feld), zwei echte Risiken, die es bei Aufgaben nie gab: (1) ein
    Admin könnte eine Spalte umbenennen/löschen, deren Wortlaut in den KPI-Auswertungen fest
    verdrahtet ist, wodurch eine Kennzahl lautlos falsch würde, nicht nur die Kanban-Anzeige;
    (2) ein von Hand verschobenes Projekt würde beim nächsten automatischen Schreibvorgang
    (Beauftragung, Resync) unbemerkt wieder zurückspringen. `pipeline_column_id` ist deshalb
    eine rein freie, vom Nutzer per Ziehen gesetzte Arbeitsansicht ohne jede fachliche
    Bedeutung -- KEINE Funktion dieses Projekts leitet `status` aus ihr ab oder überschreibt
    sie automatisch. Wer diese beiden Felder später zusammenlegen will, bricht damit die
    bestehende Statusautomatik/Kennzahlenauswertung -- siehe CLAUDE.md "Projekt-Pipeline"
    für die vollständige Herleitung dieser Entscheidung.

    Bewusst nach demselben Muster wie TaskColumn aufgebaut (key/label/sort_order, siehe dort),
    aber OHNE is_done -- die Pipeline-Spalte trägt keine Automatik (anders als
    TaskColumn.is_done -> Task.completed_at), ein "erledigt"-Flag ohne Wirkung wäre nur
    irreführend. Eine gemeinsame, generische Abstraktion für nur diese zwei Nutzer (Task
    verweist über den String-Schlüssel Task.status == TaskColumn.key, Project dagegen über die
    numerische ID Project.pipeline_column_id == ProjectPipelineColumn.id -- zwei
    unterschiedliche Referenzformen) wurde bewusst nicht gebaut, siehe
    app/project_pipeline_columns.py."""

    __tablename__ = "project_pipeline_columns"
    __table_args__ = (UniqueConstraint("key", name="uq_project_pipeline_column_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectProfile(Base):
    """Erweiterbare Projektstammdaten ohne ALTER TABLE an bestehenden Installationen.

    source_maintenance_contract_id/source_maintenance_contract_item_id (seit 1.2.15) markieren,
    dass dieses Projekt über create_project_from_contract() aus einem Wartungsvertrag (bzw.
    einer seiner Positionen) entstanden ist -- der Weg, wie der Vertragsbezug bis zum
    ServiceReport durchgereicht wird, ohne Order anzufassen (siehe create_report() in
    app/service_reports.py). duplicate_project() kopiert diese beiden Felder bewusst NICHT auf
    ein Duplikat (siehe dort)."""

    __tablename__ = "project_profiles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_project_profile_project"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_maintenance_contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_contracts.id"), nullable=True, index=True
    )
    source_maintenance_contract_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_contract_items.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="profile")


class DocumentCategory(Base):
    """Echte Stammdatentabelle für Dokumentkategorien (seit 1.3.62, Fundament für die
    Dateiablage je Objekt, siehe CLAUDE.md "Dateiablage je Objekt") -- löst die bisherige freie
    Optionsgruppe project_document_categories ab (galt für Kunden- UND Projektmappe). Dieselbe
    Hochstufung SettingOptionGroup -> echte Tabelle wie bei RoofComponentType/RoofLayerType
    (1.2.19/1.2.18): eine reine Options-Auswahlliste konnte is_sensitive/is_field_visible nicht
    tragen. key bleibt bewusst textidentisch zu den bisherigen Options-Werten ("Pläne",
    "Rechnungen / Belege", ...), damit CustomerDocument.category/ProjectDocument.category (beide
    weiterhin einfache Strings, siehe dort) unverändert weiter funktionieren -- category_id ist
    ein zusätzliches, aus dem String aufgelöstes Feld, kein Ersatz dafür.

    is_sensitive ist EINMAL auf True gesetzt UNVERÄNDERLICH -- kann über update_category()
    (app/document_categories.py) nie wieder auf False zurückgesetzt werden. is_field_visible
    kann bei is_sensitive=True gar nicht erst True werden -- diese Kombination wird sowohl in
    create_category() als auch in update_category() abgelehnt, nicht nur in der Oberfläche.
    Zusätzlich gibt es eine zweite, unabhängige Sperre: HARD_LOCKED_CATEGORY_KEYS
    (app/document_categories.py) -- "Rechnungen / Belege" und "Verträge / Freigaben" sind dort
    fest im Code eingetragen und bleiben für Monteure gesperrt, selbst wenn jemand is_sensitive/
    is_field_visible direkt in der Datenbank manipuliert (field_may_see_category() prüft beide
    Sperren unabhängig voneinander -- zwei Schlösser, kein gemeinsamer Schlüssel)."""

    __tablename__ = "document_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    label: Mapped[str] = mapped_column(String(120))
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_field_visible: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectDocument(Base):
    """Datei in einer Projektmappe. Die Datei selbst liegt im lokalen Projektspeicher.

    subfolder (seit 1.0.54, Dokumentenmanagement): frei eingebbarer, optionaler
    Unterordner-Name innerhalb der festen category -- rein organisatorisch in
    der Datenbank, es gibt keinen tatsächlichen Unterordner auf der Festplatte
    (Dateien liegen ohnehin flach unter einer zufälligen UUID je Projekt,
    siehe stored_filename/document_path()). Bewusst kein eigenes Modell/keine
    eigene Verwaltungstabelle für Unterordner: sie entstehen einfach dadurch,
    dass jemand beim Hochladen einen Namen einträgt, und verschwinden wieder,
    sobald keine Datei mehr darauf verweist -- genau wie ein Dateisystem-Ordner
    ohne Inhalt.

    category_id (seit 1.3.62, siehe CLAUDE.md "Dateiablage je Objekt"): aus category
    aufgelöste Fremdschlüsselbeziehung auf die neue Stammdatentabelle DocumentCategory --
    category selbst bleibt der freie String und alleinige Quelle beim Hochladen/Ändern,
    category_id wird von den Endpunkten in app/routers/projects.py/project_documents.py
    zusätzlich MITGESETZT (nie umgekehrt), damit is_sensitive/is_field_visible je Datei
    nachschlagbar sind, ohne category als Text zu duplizieren oder zu ersetzen."""

    __tablename__ = "project_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    category: Mapped[str] = mapped_column(String(100), default="Sonstiges", index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("document_categories.id"), index=True)
    subfolder: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    file_size: Mapped[int] = mapped_column(default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    project: Mapped[Project] = relationship(back_populates="documents")
    document_category: Mapped["DocumentCategory"] = relationship()


class CustomerDocument(Base):
    """Datei in der Kundenmappe (seit 1.0.54, Dokumentenmanagement) --
    strukturell bewusst identisch zu ProjectDocument (category + subfolder,
    dieselbe zufällige stored_filename-Ablage, dieselbe Kategorie-Auswahlliste
    project_document_categories), nur mit customer_id statt project_id.

    Bewusst ein eigenes Modell statt eine polymorphe owner_type/owner_id-Spalte
    auf einer gemeinsamen Tabelle: eine echte Fremdschlüsselbeziehung zu genau
    einer Tabelle ist einfacher zu warten und in SQLite besser indexierbar als
    ein manuell gepflegter, nicht durch die Datenbank erzwungener Bezug. Die
    bestehende ProjectDocument-Tabelle bleibt dabei unangetastet -- keine
    riskante Umbenennung/Migration einer Tabelle, die bereits echte Dateien auf
    der Festplatte referenziert.

    category_id (seit 1.3.62): dieselbe Ergänzung wie bei ProjectDocument.category_id, siehe
    dort für die volle Begründung."""

    __tablename__ = "customer_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    category: Mapped[str] = mapped_column(String(100), default="Sonstiges", index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("document_categories.id"), index=True)
    subfolder: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    file_size: Mapped[int] = mapped_column(default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    customer: Mapped["Customer"] = relationship(back_populates="documents")
    document_category: Mapped["DocumentCategory"] = relationship()


class PropertyDocument(Base):
    """Datei, die direkt an einem Objekt (Property) hängt -- seit "Dateiablage je Objekt"
    (siehe CLAUDE.md), Runde 2 der Monteurs-Erweiterung. Trägt vor allem die eigenen Uploads
    eines Monteurs vor Ort: ein spontaner Einsatz hat oft gar kein Projekt, ProjectDocument kann
    solche Uploads deshalb nicht aufnehmen -- die Entscheidung war explizit objektbezogene
    Ablage statt eines Sammelprojekts je Objekt (siehe CLAUDE.md "Dateiablage je Objekt" für die
    volle Begründung, u. a. dass ein Sammelprojekt in jeder projektbezogenen Auswertung
    fälschlich als echter Auftrag/Angebot mitgezählt worden wäre). Das Büro sieht/verwaltet
    dieselbe Tabelle zusätzlich über eine eigene Objektseiten-Sektion -- diese Datei ist NICHT
    monteur-exklusiv, nur monteur-tauglich.

    Anders als ProjectDocument/CustomerDocument trägt diese neue Tabelle bewusst NUR category_id,
    keinen zusätzlichen freien category-String: dort existiert category als Freitext nur, weil
    beim Hochstufen zu DocumentCategory (1.3.62) bereits bestehende Freitext-Werte weiter matchen
    mussten -- für eine brandneue Tabelle ohne Altbestand gibt es diesen Zwang nicht, ein
    zusätzliches Freitextfeld wäre hier nur eine potenzielle zweite Quelle der Wahrheit.

    uploaded_by_employee_id ist von Anfang an gehärtet vorgesehen (Muster
    _employee_for_request()/app/routers/service_reports.py) -- ein Monteur darf beim Hochladen
    nur die eigene employee_id angeben, nie eine fremde; Büro-Uploads bleiben NULL oder tragen
    die eigene, freiwillig gesetzte Mitarbeiter-ID."""

    __tablename__ = "property_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("document_categories.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    file_size: Mapped[int] = mapped_column(default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    uploaded_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    property: Mapped["Property"] = relationship(back_populates="documents")
    document_category: Mapped["DocumentCategory"] = relationship()
    uploaded_by_employee: Mapped["Employee | None"] = relationship()


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (UniqueConstraint("quote_number", name="uq_quote_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_number: Mapped[str] = mapped_column(String(50), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="entwurf", index=True)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("19.00"))
    tax_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("tax_keys.id", name="fk_quotes_tax_key_id"), nullable=True, index=True
    )
    intro_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    outro_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    outro_text_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_format: Mapped[str] = mapped_column(String(50), default="manual")
    gaeb_exchange_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Versand-Nachweis (seit 1.0.87) -- analog zu Invoice/Reminder, auch wenn
    # Angebote (anders als Rechnung/Mahnung) keinen GoBD-artigen
    # Unveränderlichkeits-Mechanismus haben. quote_number existiert bereits
    # ab Anlage, nicht erst ab einer Finalisierung -- email_sent_at/
    # email_sent_to bleiben trotzdem sinnvoll, um nachzuhalten, ob und an
    # wen ein Angebot tatsächlich verschickt wurde.
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_sent_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="quotes")
    items: Mapped[list["QuoteItem"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", order_by="QuoteItem.sort_order"
    )


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    source_service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    position_number: Mapped[str] = mapped_column(String(50))
    gaeb_oz: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position_type: Mapped[str] = mapped_column(String(30), default="normal")

    source_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    short_text: Mapped[str] = mapped_column(Text)
    long_text: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(50))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    source_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    quote: Mapped[Quote] = relationship(back_populates="items")
    source_service: Mapped[Service | None] = relationship()
    project_calculation: Mapped["QuoteItemCalculation | None"] = relationship(
        back_populates="quote_item", cascade="all, delete-orphan", uselist=False
    )


class QuoteItemCalculation(Base):
    """Projektbezogene Kalkulationskopie einer Angebotsposition.

    Änderungen hier betreffen ausschließlich das konkrete Angebot und niemals
    die Katalogleistung.
    """

    __tablename__ = "quote_item_calculations"
    __table_args__ = (UniqueConstraint("quote_item_id", name="uq_quote_item_calculation_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_item_id: Mapped[int] = mapped_column(ForeignKey("quote_items.id"), index=True)
    site_time_minutes: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    workshop_time_minutes: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    labor_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    material_markup_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    equipment_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    subcontractor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    other_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    overhead_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    risk_profit_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    manual_sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    quote_item: Mapped[QuoteItem] = relationship(back_populates="project_calculation")
    materials: Mapped[list["QuoteItemMaterialCalculation"]] = relationship(
        back_populates="calculation", cascade="all, delete-orphan", order_by="QuoteItemMaterialCalculation.id"
    )


class QuoteItemMaterialCalculation(Base):
    __tablename__ = "quote_item_material_calculations"

    id: Mapped[int] = mapped_column(primary_key=True)
    calculation_id: Mapped[int] = mapped_column(ForeignKey("quote_item_calculations.id"), index=True)
    source_material_id: Mapped[int | None] = mapped_column(ForeignKey("service_materials.id"), nullable=True)
    name: Mapped[str] = mapped_column(Text)
    article_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(50))
    source_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    waste_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    source_purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    price_basis: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))

    calculation: Mapped[QuoteItemCalculation] = relationship(back_populates="materials")


class QuoteDocumentMeta(Base):
    """Erweiterter Angebotskopf ohne ALTER TABLE auf bestehenden Installationen."""

    __tablename__ = "quote_document_meta"
    __table_args__ = (UniqueConstraint("quote_id", name="uq_quote_document_meta_quote"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    quote_date: Mapped[date] = mapped_column(Date, default=date.today)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_period: Mapped[str | None] = mapped_column(String(255), nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QuoteSection(Base):
    """Titel/Untertitel eines Leistungsverzeichnisses. Maximal zwei Ebenen in 0.6."""

    __tablename__ = "quote_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("quote_sections.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    section_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QuoteItemLayout(Base):
    """LV-Platzierung einer Angebotsposition, getrennt von der Kalkulationsposition."""

    __tablename__ = "quote_item_layouts"
    __table_args__ = (UniqueConstraint("quote_item_id", name="uq_quote_item_layout_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_item_id: Mapped[int] = mapped_column(ForeignKey("quote_items.id"), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("quote_sections.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    include_in_total: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Order(Base):
    """Auftrag / Auftragsbestätigung als unveränderlicher LV-Snapshot eines Angebots."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_number", name="uq_order_number"),
        UniqueConstraint("source_quote_id", name="uq_order_source_quote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(50), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    source_quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    quote_number_snapshot: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="beauftragt", index=True)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("19.00"))
    tax_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("tax_keys.id", name="fk_orders_tax_key_id"), nullable=True, index=True
    )
    intro_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    outro_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    outro_text_2: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Snapshot der Adress-/Kundendaten zum Zeitpunkt der Beauftragung.
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    property_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    property_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    order_date: Mapped[date] = mapped_column(Date, default=date.today)
    execution_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    execution_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    caseworker_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    project_manager_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    # Versand-Nachweis (seit 1.0.90) -- analog zu Invoice/Quote/Reminder.
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_sent_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="orders")
    source_quote: Mapped[Quote] = relationship()
    sections: Mapped[list["OrderSection"]] = relationship(back_populates="order", cascade="all, delete-orphan", order_by="OrderSection.sort_order")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.sort_order")
    revisions: Mapped[list["OrderRevision"]] = relationship(back_populates="order", cascade="all, delete-orphan", order_by="OrderRevision.revision_number")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    caseworker: Mapped["Employee | None"] = relationship(foreign_keys=[caseworker_employee_id])
    project_manager: Mapped["Employee | None"] = relationship(foreign_keys=[project_manager_employee_id])


class OrderRevision(Base):
    """Versionierter Auftragsstand. Der aktuelle Auftrag bleibt bearbeitbar;
    Revisionen sichern freigegebene bzw. synchronisierte Zwischenstände.
    """

    __tablename__ = "order_revisions"
    __table_args__ = (UniqueConstraint("order_id", "revision_number", name="uq_order_revision_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    revision_number: Mapped[int] = mapped_column(default=1)
    reason: Mapped[str] = mapped_column(String(255), default="Auftragsstand gesichert")
    source: Mapped[str] = mapped_column(String(50), default="manual")
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str] = mapped_column(String(160), default="System")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    order: Mapped[Order] = relationship(back_populates="revisions")


class OrderSection(Base):
    __tablename__ = "order_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("order_sections.id"), nullable=True, index=True)
    source_quote_section_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    section_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    order: Mapped[Order] = relationship(back_populates="sections")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("order_sections.id"), nullable=True, index=True)
    source_quote_item_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    position_number: Mapped[str] = mapped_column(String(50))
    gaeb_oz: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position_type: Mapped[str] = mapped_column(String(30), default="normal")
    source_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    short_text: Mapped[str] = mapped_column(Text)
    long_text: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(50))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    include_in_total: Mapped[bool] = mapped_column(Boolean, default=True)

    order: Mapped[Order] = relationship(back_populates="items")
    calculation_snapshot: Mapped["OrderItemCalculationSnapshot | None"] = relationship(back_populates="order_item", cascade="all, delete-orphan", uselist=False)


class OrderItemCalculationSnapshot(Base):
    """Unveränderliche Kalkulationsbasis der beauftragten Position für AV/Nachkalkulation."""
    __tablename__ = "order_item_calculation_snapshots"
    __table_args__ = (UniqueConstraint("order_item_id", name="uq_order_item_calc_snapshot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), index=True)
    site_time_minutes: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    workshop_time_minutes: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    labor_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    material_markup_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    equipment_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    subcontractor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    other_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    overhead_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    risk_profit_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    effective_sale_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    order_item: Mapped[OrderItem] = relationship(back_populates="calculation_snapshot")
    materials: Mapped[list["OrderItemMaterialSnapshot"]] = relationship(back_populates="calculation", cascade="all, delete-orphan", order_by="OrderItemMaterialSnapshot.id")


class OrderItemMaterialSnapshot(Base):
    __tablename__ = "order_item_material_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    calculation_id: Mapped[int] = mapped_column(ForeignKey("order_item_calculation_snapshots.id"), index=True)
    article_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    waste_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    price_basis: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))

    calculation: Mapped[OrderItemCalculationSnapshot] = relationship(back_populates="materials")


class Invoice(Base):
    """Rechnung zu einem Auftrag (seit 1.0.33). Ein Auftrag kann mehrere
    Rechnungen haben: Abschlagsrechnungen (pauschal oder nach Leistungsstand),
    eine Schlussrechnung, und ggf. Stornorechnungen zu bereits versendeten
    Rechnungen.

    invoice_number bleibt NULL, solange status='entwurf' -- die Nummer aus
    dem Nummernkreis wird erst beim Versenden vergeben (siehe issue_invoice()
    in app/invoices.py), damit verworfene Entwürfe keine Lücken in der
    Nummernfolge hinterlassen (GoBD-Anforderung an lückenlose Rechnungsnummern).
    Ab 'versendet' gilt die Rechnung als unveränderlich, genau wie ein Auftrag
    nach Beauftragung."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    invoice_type: Mapped[str] = mapped_column(String(30), index=True)  # 'abschlag_pauschal' | 'abschlag_leistungsstand' | 'schluss' | 'storno'
    status: Mapped[str] = mapped_column(String(20), default="entwurf", index=True)  # 'entwurf' | 'versendet' | 'bezahlt' | 'storniert'
    invoice_date: Mapped[date] = mapped_column(Date, default=date.today)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Bei invoice_type='storno': welche Rechnung wird hiermit storniert. Bewusst
    # nur als FK-Spalte, ohne eigene ORM-Relationship -- vermeidet Komplexität
    # durch die Selbstreferenz, wird bei Bedarf direkt abgefragt.
    storno_of_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True, index=True)

    # Schnappschuss der Kunden-/Objektdaten zum Zeitpunkt des Versendens, wie beim Auftrag.
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    property_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    property_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    vat_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("19.00"))
    # Schnappschuss des gewählten Steuerschlüssels zum Erstellzeitpunkt (seit
    # 1.0.44) -- wie bei Skonto bewusst eingefroren statt live von TaxKey
    # nachgeladen: derselbe Grund, eine spätere Änderung des Hinweistexts
    # darf eine bereits versendete Rechnung nicht rückwirkend verändern.
    tax_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("tax_keys.id", name="fk_invoices_tax_key_id"), nullable=True, index=True
    )
    tax_notice_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Nur bei invoice_type='abschlag_pauschal' genutzt -- direkt eingetragener Betrag, alleinige
    # Quelle der Wahrheit fuer den Rechnungsbetrag (compute_invoice_totals()). Seit 1.3.24 zusaetzlich
    # in EINER InvoiceItem-Zeile gespiegelt, damit PDF/Anzeige eine Position mit Beschreibung
    # zeigen koennen -- siehe InvoiceItem-Docstring, diese Zeile bleibt die massgebliche Zahl.
    lump_sum_net: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    progress_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    intro_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    outro_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    outro_text_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Schnappschuss der Skonto-Regelung zum Erstellzeitpunkt (seit 1.0.41) --
    # bewusst auf der Rechnung eingefroren, nicht live von PaymentTerm
    # nachgeladen: eine spätere Änderung/Archivierung der Zahlungsbedingung
    # darf eine bereits versendete Rechnung nicht rückwirkend verändern.
    skonto_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    skonto_days: Mapped[int | None] = mapped_column(nullable=True)
    payment_terms_text_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    caseworker_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    # Versand-Nachweis (seit 1.0.82) -- analog zu Reminder.email_sent_at/
    # email_sent_to: getrennt vom Rechnungsstatus selbst, eine Rechnung kann
    # finalisiert, aber noch nie oder mehrfach per E-Mail verschickt worden
    # sein (erneuter Versand z.B. falls der Kunde sie nicht erhalten hat).
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_sent_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order: Mapped["Order"] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.sort_order")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="invoice", cascade="all, delete-orphan", order_by="Reminder.level")


class InvoiceItem(Base):
    """Rechnungsposition.

    invoice_type='abschlag_pauschal' (seit 1.3.24, vorher gar keine Position -- siehe CLAUDE.md
    "Pauschale Abschlagsrechnung ohne Positionstabelle") trägt GENAU EINE Zeile, die eine REINE
    PROJEKTION von Invoice.lump_sum_net/progress_description ist -- niemals eine eigenständige,
    unabhängig editierbare Position. _sync_lump_sum_pauschal_item() in app/invoices.py hält sie
    synchron; add_invoice_item()/update_invoice_item()/remove_invoice_item() lehnen jede Änderung
    an dieser Zeile über den allgemeinen Positionsweg ab. compute_invoice_totals() liest für
    diesen Typ weiterhin ausschließlich lump_sum_net, nie eine Positionssumme -- die Zeile dient
    ausschließlich der Anzeige (PDF/API), niemals der Betragsberechnung. Bei
    'abschlag_leistungsstand'/'schluss'/'storno' dagegen die normale, mehrzeilige Positionsliste.

    Soll/Ist-Mechanik: soll_quantity kommt informativ aus der Auftragsposition
    (source_order_item_id) und ändert sich nicht. ist_quantity ist der
    KUMULIERTE Stand zum Zeitpunkt DIESER Rechnung (z.B. "80 von 100 m²
    insgesamt fertig"), nicht nur der Anteil dieser Rechnung. billed_quantity/
    billed_total sind die Differenz zum kumulierten Stand der letzten
    vorherigen, bereits versendeten Rechnung für dieselbe Auftragsposition --
    das, was auf DIESER Rechnung tatsächlich in Rechnung gestellt wird (siehe
    berechne_abgerechnete_menge() in app/invoices.py). Bei neuen Positionen
    ohne Auftragsbezug (Nachträge) ist source_order_item_id NULL und die
    komplette ist_quantity wird abgerechnet, da es keinen vorherigen Stand
    gibt.

    Positionen mit ist_quantity=0 werden auf der Rechnung selbst nicht
    angezeigt (siehe PDF-/Anzeigelogik), bleiben aber für die Soll/Ist-Historie
    in der Datenbank bestehen."""

    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    source_order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    position_number: Mapped[str] = mapped_column(String(50))
    gaeb_oz: Mapped[str | None] = mapped_column(String(100), nullable=True)
    short_text: Mapped[str] = mapped_column(Text)
    long_text: Mapped[str] = mapped_column(Text, default="")
    unit: Mapped[str] = mapped_column(String(50))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    soll_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ist_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    billed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    billed_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class ReminderLevel(Base):
    """Mahnstufen-Einstellung (seit 1.0.53) -- bis zu drei konfigurierbare
    Stufen (1./2./3. Mahnung), jede einzeln über `active` aktivierbar,
    damit frei wählbar bleibt, wie viele Stufen tatsächlich genutzt werden
    (Klärung dazu: "bis 3 Stufen, aber auswählbar wie viele man
    tatsächlich nutzt").

    days_after_previous_step ist die Frist in Tagen, ab der diese Stufe
    fällig wird -- bei Stufe 1 gerechnet ab der Fälligkeit der Rechnung
    selbst, bei Stufe 2/3 ab dem Versanddatum der jeweils vorherigen
    Mahnung (siehe compute_reminder_status() in app/reminders.py).

    fee_amount ist die Mahngebühr dieser Stufe in Euro. Bewusst ohne
    eigenen Steuersatz: Mahngebühren gelten umsatzsteuerlich in der Regel
    als Schadensersatz, nicht als Leistung, und werden daher hier als
    eigene, umsatzsteuerfreie Position geführt -- das ist eine bewusste
    fachliche Voreinstellung, keine verbindliche Steuerauskunft; bitte im
    Zweifel mit eurem Steuerberater abstimmen."""

    __tablename__ = "reminder_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[int] = mapped_column(index=True)  # 1, 2 oder 3
    label: Mapped[str] = mapped_column(String(120))
    days_after_previous_step: Mapped[int] = mapped_column(default=7)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    text_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    # E-Mail-Textbausteine (seit 1.0.74) -- bewusst getrennt von
    # text_template (das für den PDF-Inhalt gilt): die E-Mail selbst soll
    # eine kurze, eigenständige Nachricht sein, die Details stehen im
    # PDF-Anhang. NULL bedeutet "noch nicht angepasst", die
    # Versandfunktion nutzt dann einen eingebauten Standardtext -- so
    # bleibt die Spalte nullable (kein server_default nötig) und trotzdem
    # funktioniert der Versand auch ohne manuelle Anpassung sofort.
    email_subject_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_body_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Reminder(Base):
    """Mahnung zu einer überfälligen Rechnung (seit 1.0.53). Analog zu
    Invoice: reminder_number bleibt NULL, solange status='entwurf', wird
    erst beim Finalisieren aus dem Nummernkreis vergeben (siehe
    finalize_reminder() in app/reminders.py) -- aus demselben GoBD-Grund
    wie bei Rechnungen (lückenlose Nummernfolge, kein verworfener Entwurf
    hinterlässt eine Lücke).

    Bewusst keine eigene Positionsliste und keine eigenen
    Kunden-/Objektadress-Schnappschüsse: eine Mahnung bezieht sich auf
    genau eine bereits versendete (und damit unveränderliche) Rechnung --
    Kunden-/Objektdaten werden direkt über invoice bezogen. outstanding_amount
    und fee_amount sind trotzdem als Schnappschuss auf der Mahnung selbst
    festgehalten (nicht live aus ReminderLevel/Invoice berechnet) -- eine
    spätere Änderung der Mahngebühr in den Einstellungen darf eine bereits
    versendete Mahnung nicht rückwirkend verändern."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    level: Mapped[int] = mapped_column(index=True)  # 1, 2 oder 3
    status: Mapped[str] = mapped_column(String(20), default="entwurf", index=True)  # 'entwurf' | 'versendet'
    reminder_date: Mapped[date] = mapped_column(Date, default=date.today)
    new_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Versand-Nachweis (seit 1.0.74) -- getrennt von status='versendet'
    # (das die fachliche Finalisierung/Nummernvergabe meint, siehe oben):
    # eine Mahnung kann finalisiert, aber noch nie oder mehrfach per E-Mail
    # verschickt worden sein (z.B. erneuter Versand, falls der Kunde sie
    # nicht erhalten hat). email_sent_to hält bewusst die tatsächlich
    # genutzte Adresse fest (kann vor dem Versand manuell korrigiert
    # worden sein), nicht nur einen Verweis auf die Kundenstammdaten.
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_sent_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    invoice: Mapped[Invoice] = relationship(back_populates="reminders")


class WorkPreparation(Base):
    """Arbeitsvorbereitung eines beauftragten Auftrags."""
    __tablename__ = "work_preparations"
    __table_args__ = (UniqueConstraint("order_id", name="uq_work_preparation_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="offen", index=True)
    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    site_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order: Mapped[Order] = relationship()
    employees: Mapped[list["WorkPreparationEmployee"]] = relationship(back_populates="preparation", cascade="all, delete-orphan", order_by="WorkPreparationEmployee.id")
    tasks: Mapped[list["WorkPreparationTask"]] = relationship(back_populates="preparation", cascade="all, delete-orphan", order_by="WorkPreparationTask.sort_order")
    materials: Mapped[list["WorkPreparationMaterial"]] = relationship(back_populates="preparation", cascade="all, delete-orphan", order_by="WorkPreparationMaterial.id")


class WorkPreparationEmployee(Base):
    __tablename__ = "work_preparation_employees"
    __table_args__ = (UniqueConstraint("preparation_id", "employee_id", name="uq_work_prep_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("work_preparations.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    planned_hours: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    preparation: Mapped[WorkPreparation] = relationship(back_populates="employees")
    employee: Mapped["Employee"] = relationship()


class WorkPreparationTask(Base):
    __tablename__ = "work_preparation_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("work_preparations.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="offen", index=True)
    priority: Mapped[str] = mapped_column(String(30), default="normal")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    preparation: Mapped[WorkPreparation] = relationship(back_populates="tasks")
    assigned_employee: Mapped["Employee | None"] = relationship()


class WorkPreparationMaterial(Base):
    __tablename__ = "work_preparation_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("work_preparations.id"), index=True)
    source_material_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("order_item_material_snapshots.id"), nullable=True, index=True)
    source_order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"), nullable=True, index=True)
    article_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(50))
    calculated_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(40), default="bedarf", index=True)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    preparation: Mapped[WorkPreparation] = relationship(back_populates="materials")


class Supplier(Base):
    """Lieferanten-Stammdaten für Einkauf, Arbeitsvorbereitung und spätere Belegverarbeitung."""
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("supplier_number", name="uq_supplier_number"),
        UniqueConstraint("legacy_address_number", name="uq_supplier_legacy_address_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(120), default="Deutschland")
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_number_at_supplier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Seit dem Adressimport aus dem Altsystem (siehe CLAUDE.md) -- dieselbe Bedeutung wie
    # Customer.legacy_address_number/import_run_id.
    legacy_address_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ImportRun(Base):
    """Ein Lauf des Adressimports aus dem Altsystem (siehe CLAUDE.md "Adressimport aus dem
    Altsystem"). Jeder dabei erzeugte Customer/Supplier sowie jede ImportedAddress-Zeile
    trägt diese id -- damit lässt sich ein Lauf sowohl nachvollziehen als auch (solange an
    den erzeugten Kunden/Lieferanten noch nichts hängt) vollständig rückgängig machen."""

    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_filename: Mapped[str] = mapped_column(String(255))
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    row_count_total: Mapped[int] = mapped_column(default=0)
    row_count_customers: Mapped[int] = mapped_column(default=0)
    row_count_suppliers: Mapped[int] = mapped_column(default=0)
    row_count_unassigned: Mapped[int] = mapped_column(default=0)
    row_count_skipped_duplicates: Mapped[int] = mapped_column(default=0)
    # "completed" | "reverted" -- ein Lauf im Vorschau-Zustand (noch nicht bestätigt)
    # existiert nur als ImportedAddress-Zeilen mit status="previewing", siehe dort;
    # eine ImportRun-Zeile entsteht erst mit der Bestätigung.
    status: Mapped[str] = mapped_column(String(20), default="completed")
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    rows: Mapped[list["ImportedAddress"]] = relationship(back_populates="import_run")


class ImportedAddress(Base):
    """Eine Zeile aus einer importierten Altsystem-Adressdatei -- sowohl während der
    Vorschau (status="previewing", vor Bestätigung, noch ohne ImportRun) als auch danach
    dauerhaft als Ablage: für Kunden/Lieferanten-Zeilen als Herkunftsnachweis, für nicht
    zuordenbare Zeilen (classification="unassigned") als die in CLAUDE.md beschriebene
    Arbeitsliste, bis sie manuell aufgelöst werden. Bleibt auch nach dem Auflösen/Verwerfen
    bestehen (nie gelöscht außer beim Rückgängigmachen des ganzen Laufs) -- sonst würde ein
    erneuter Import derselben Datei dieselbe Adressnummer fälschlich als neu erkennen."""

    __tablename__ = "imported_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)
    row_number: Mapped[int] = mapped_column()
    legacy_address_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    customer_number_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supplier_number_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salutation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "customer" | "supplier" | "unassigned" | "duplicate" | "invalid"
    classification: Mapped[str] = mapped_column(String(20))
    # "previewing" | "confirmed" -- previewing-Zeilen ohne Bestätigung werden vor dem
    # Erzeugen einer neuen Vorschau verworfen (siehe app/address_import.py), zählen daher
    # nie für die Wiedererkennung bereits importierter Adressnummern.
    status: Mapped[str] = mapped_column(String(20), default="previewing")
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Nur für classification="unassigned": Ergebnis der manuellen Bearbeitung der
    # Arbeitsliste. None = noch offen (erscheint in der Arbeitsliste).
    resolution: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    created_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    created_property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    import_run: Mapped["ImportRun | None"] = relationship(back_populates="rows")


class OperationalResource(Base):
    """Planbare Ressource wie Fahrzeug, Maschine, Anhänger oder Gerät."""
    __tablename__ = "operational_resources"
    __table_args__ = (UniqueConstraint("resource_number", name="uq_operational_resource_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), default="Maschine", index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    identifier: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Team(Base):
    """Stamm-Kolonne/Team für spätere Planungstafel und Arbeitsvorbereitung."""
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("team_number", name="uq_team_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employees: Mapped[list["TeamEmployee"]] = relationship(back_populates="team", cascade="all, delete-orphan", order_by="TeamEmployee.id")
    resources: Mapped[list["TeamResource"]] = relationship(back_populates="team", cascade="all, delete-orphan", order_by="TeamResource.id")


class TeamEmployee(Base):
    __tablename__ = "team_employees"
    __table_args__ = (UniqueConstraint("team_id", "employee_id", name="uq_team_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)

    team: Mapped[Team] = relationship(back_populates="employees")
    employee: Mapped["Employee"] = relationship()


class TeamResource(Base):
    __tablename__ = "team_resources"
    __table_args__ = (UniqueConstraint("team_id", "resource_id", name="uq_team_resource"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("operational_resources.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)

    team: Mapped[Team] = relationship(back_populates="resources")
    resource: Mapped[OperationalResource] = relationship()


class WorkPreparationTeamAssignment(Base):
    """Einer AV zugewiesenes Team. Besetzung wird beim Zuweisen in Snapshot-Tabellen festgehalten."""
    __tablename__ = "work_preparation_team_assignments"
    __table_args__ = (UniqueConstraint("preparation_id", "team_id", name="uq_work_prep_team"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("work_preparations.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    team_name_snapshot: Mapped[str] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team: Mapped[Team] = relationship()
    employees: Mapped[list["WorkPreparationTeamEmployee"]] = relationship(cascade="all, delete-orphan", order_by="WorkPreparationTeamEmployee.id")
    resources: Mapped[list["WorkPreparationTeamResource"]] = relationship(cascade="all, delete-orphan", order_by="WorkPreparationTeamResource.id")


class WorkPreparationTeamEmployee(Base):
    __tablename__ = "work_preparation_team_employees"
    __table_args__ = (UniqueConstraint("assignment_id", "employee_id", name="uq_work_prep_team_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("work_preparation_team_assignments.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    employee_name_snapshot: Mapped[str] = mapped_column(String(255))
    role_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employee: Mapped["Employee"] = relationship()


class WorkPreparationTeamResource(Base):
    __tablename__ = "work_preparation_team_resources"
    __table_args__ = (UniqueConstraint("assignment_id", "resource_id", name="uq_work_prep_team_resource"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("work_preparation_team_assignments.id"), index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("operational_resources.id"), index=True)
    resource_name_snapshot: Mapped[str] = mapped_column(String(255))
    resource_type_snapshot: Mapped[str] = mapped_column(String(50))
    role_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resource: Mapped[OperationalResource] = relationship()


class PlanningSlot(Base):
    """Zeitlicher Einsatz einer Kolonne in der zentralen Planungstafel.

    Die Besetzung und Ressourcen stammen aus dem Snapshot der
    WorkPreparationTeamAssignment. Ein Auftrag kann damit mehrere Kolonnen
    und auch mehrere getrennte Zeitblöcke je Kolonne besitzen.
    """
    __tablename__ = "planning_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("work_preparations.id"), index=True)
    team_assignment_id: Mapped[int] = mapped_column(ForeignKey("work_preparation_team_assignments.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(40), default="geplant", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    preparation: Mapped[WorkPreparation] = relationship()
    team_assignment: Mapped[WorkPreparationTeamAssignment] = relationship()
    capacity: Mapped["PlanningSlotCapacity | None"] = relationship(back_populates="slot", cascade="all, delete-orphan", uselist=False)


class PlanningSettings(Base):
    """Zentrale Planungs- und Kapazitätsparameter der Plantafel."""
    __tablename__ = "planning_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    daily_work_hours: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("8.00"))
    default_travel_hours_per_employee_day: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0.00"))
    monday: Mapped[bool] = mapped_column(Boolean, default=True)
    tuesday: Mapped[bool] = mapped_column(Boolean, default=True)
    wednesday: Mapped[bool] = mapped_column(Boolean, default=True)
    thursday: Mapped[bool] = mapped_column(Boolean, default=True)
    friday: Mapped[bool] = mapped_column(Boolean, default=True)
    saturday: Mapped[bool] = mapped_column(Boolean, default=False)
    sunday: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)




class PlanningRegionSettings(Base):
    """Bundesland und automatische Kalenderdaten für die Plantafel."""
    __tablename__ = "planning_region_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    federal_state_code: Mapped[str] = mapped_column(String(2), default="NW")
    auto_public_holidays: Mapped[bool] = mapped_column(Boolean, default=True)
    show_school_holidays: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlanningSchoolHoliday(Base):
    """Zwischengespeicherte Schulferien für die rein visuelle Darstellung in der Plantafel."""
    __tablename__ = "planning_school_holidays"
    __table_args__ = (
        UniqueConstraint("state_code", "calendar_year", "name", "start_date", "end_date", name="uq_planning_school_holiday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2), index=True)
    calendar_year: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(80), default="ferien-api.de")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlanningSchoolHolidaySync(Base):
    """Merkt, ob ein Kalenderjahr für ein Bundesland bereits automatisch synchronisiert wurde."""
    __tablename__ = "planning_school_holiday_sync"
    __table_args__ = (UniqueConstraint("state_code", "calendar_year", name="uq_planning_school_holiday_sync"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2), index=True)
    calendar_year: Mapped[int] = mapped_column(index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PlanningHoliday(Base):
    """Feiertage und betriebsfreie Tage, die keine Planungskapazität bereitstellen."""
    __tablename__ = "planning_holidays"
    __table_args__ = (UniqueConstraint("holiday_date", name="uq_planning_holiday_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    holiday_date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(180))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmployeeAbsence(Base):
    """Ganztägige Abwesenheit eines Mitarbeiters für Urlaub, Krankheit usw.

    absence_category (seit "Schlechtwetter/Krankheit-Trennung") ist die feste, vier Werte
    umfassende Klassifikation (urlaub/krankheit/fortbildung/unbezahlt, siehe
    app/absence_requests.py::ABSENCE_CATEGORIES) -- ein fester Code-Wert wie
    RecurringCost.overhead_classification, KEINE Optionsgruppe, da eine spätere Ist-Wert-
    Auswertung wissen muss, welche Werte existieren. absence_type bleibt UNVERÄNDERT das
    freie, über die Optionsgruppe absence_types gepflegte Ergänzungsfeld daneben (z. B.
    "Berufsschule" als Unterfall von "fortbildung") -- keine Ablösung. "unbekannt" ist der
    Migrations-Rückfallwert für Altbestand ohne Kategorie und beim Neuanlegen NICHT wählbar
    (Schema-Pattern lässt nur die vier echten Werte zu) -- eine spätere Ist-Wert-Auswertung
    zählt "unbekannt" bewusst nicht mit.
    """
    __tablename__ = "employee_absences"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    absence_type: Mapped[str] = mapped_column(String(80), default="Urlaub", index=True)
    absence_category: Mapped[str] = mapped_column(String(20), default="unbekannt", server_default="unbekannt", index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee: Mapped["Employee"] = relationship()


class EmployeeAbsenceRequest(Base):
    """Abwesenheitsantrag eines Mitarbeiters mit Freigabeprozess.

    Erst bei Freigabe wird eine EmployeeAbsence erzeugt, damit Plantafel und
    Kapazitaetsplanung nur genehmigte Abwesenheiten berücksichtigen.
    """
    __tablename__ = "employee_absence_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    absence_type: Mapped[str] = mapped_column(String(80), default="Urlaub", index=True)
    absence_category: Mapped[str] = mapped_column(String(20), default="unbekannt", server_default="unbekannt", index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_absence_id: Mapped[int | None] = mapped_column(ForeignKey("employee_absences.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee: Mapped["Employee"] = relationship(foreign_keys=[employee_id])
    approved_absence: Mapped["EmployeeAbsence | None"] = relationship(foreign_keys=[approved_absence_id])


class PlanningSlotCapacity(Base):
    """Additive Kapazitätswerte eines Planeinsatzes ohne ALTER TABLE auf Bestandsdatenbanken."""
    __tablename__ = "planning_slot_capacity"
    __table_args__ = (UniqueConstraint("slot_id", name="uq_planning_slot_capacity_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("planning_slots.id"), index=True)
    planned_hours: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    travel_hours_per_employee_day: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    slot: Mapped[PlanningSlot] = relationship(back_populates="capacity")


class WorkPreparationMaterialSupplier(Base):
    """Strukturierte Lieferantenzuordnung zu einer AV-Materialposition; Freitext bleibt kompatibel."""
    __tablename__ = "work_preparation_material_suppliers"
    __table_args__ = (UniqueConstraint("material_id", name="uq_work_prep_material_supplier"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("work_preparation_materials.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    supplier: Mapped[Supplier] = relationship()


class WorkPreparationDeliveryNote(Base):
    """Verknüpft einen eingescannten/hochgeladenen Lieferschein mit Projekt, AV und Lieferant."""
    __tablename__ = "work_preparation_delivery_notes"
    __table_args__ = (UniqueConstraint("project_document_id", name="uq_work_prep_delivery_document"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("work_preparations.id"), index=True)
    project_document_id: Mapped[int] = mapped_column(ForeignKey("project_documents.id"), index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True, index=True)
    delivery_note_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[ProjectDocument] = relationship()
    supplier: Mapped[Supplier | None] = relationship()


class WorkPreparationMaterialDeliveryNote(Base):
    """Many-to-many link: Materialpositionen können mehreren Lieferscheinen zugeordnet sein."""
    __tablename__ = "work_preparation_material_delivery_notes"
    __table_args__ = (UniqueConstraint("material_id", "delivery_note_id", name="uq_work_prep_material_delivery_note"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("work_preparation_materials.id"), index=True)
    delivery_note_id: Mapped[int] = mapped_column(ForeignKey("work_preparation_delivery_notes.id"), index=True)
    delivery_note: Mapped[WorkPreparationDeliveryNote] = relationship()




class TimeTrackingSettings(Base):
    """Zentrale Einstellungen des Zeiterfassungs-Backoffice."""
    __tablename__ = "time_tracking_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    rounding_minutes: Mapped[int] = mapped_column(default=0)
    default_break_minutes: Mapped[int] = mapped_column(default=0)
    allow_manual_entries: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_group_bookings: Mapped[bool] = mapped_column(Boolean, default=True)
    require_order_item: Mapped[bool] = mapped_column(Boolean, default=False)
    require_activity: Mapped[bool] = mapped_column(Boolean, default=False)
    datev_target: Mapped[str] = mapped_column(String(30), default="lohn_gehalt")
    datev_wage_type_site: Mapped[str | None] = mapped_column(String(30), nullable=True)
    datev_wage_type_travel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    datev_wage_type_workshop: Mapped[str | None] = mapped_column(String(30), nullable=True)
    datev_wage_type_other: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Schlechtwetter Winter/Sommer sind tariflich unterschiedliche Lohnarten (Saison-
    # Kurzarbeitergeld gegen Ausfallgeld) -- fallen ohne eigene Spalte auf datev_wage_type_other
    # zurueck (siehe app/time_backoffice.py::_wage_type()), was fachlich falsch waere.
    datev_wage_type_weather_winter: Mapped[str | None] = mapped_column(String(30), nullable=True)
    datev_wage_type_weather_summer: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmployeePayrollSettings(Base):
    """Lohn-/DATEV-Zuordnung eines Mitarbeiters ohne Änderung der Bestands-Mitarbeitertabelle."""
    __tablename__ = "employee_payroll_settings"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_payroll_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    datev_personnel_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    payroll_export_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TimeBackofficeAdvancedSettings(Base):
    """Erweiterte Backoffice-Einstellungen ohne ALTER TABLE auf Bestandsinstallationen."""
    __tablename__ = "time_backoffice_advanced_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    datev_personnel_equals_erp_number: Mapped[bool] = mapped_column(Boolean, default=False)
    default_work_time_model_id: Mapped[int | None] = mapped_column(ForeignKey("work_time_models.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkTimeModel(Base):
    """Konfigurierbares Arbeitszeitmodell, z. B. Sommer- oder Wintermodell."""
    __tablename__ = "work_time_models"
    __table_args__ = (UniqueConstraint("name", name="uq_work_time_model_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    daily_target_hours: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("8.00"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    break_rules: Mapped[list["WorkTimeBreakRule"]] = relationship(
        back_populates="model", cascade="all, delete-orphan", order_by="WorkTimeBreakRule.threshold_hours"
    )


class WorkTimeModelValidity(Base):
    """Kalenderwochen-Gültigkeit eines Arbeitszeitmodells ohne ALTER TABLE auf Bestandsinstallationen.

    Bereiche über den Jahreswechsel werden unterstützt, z. B. KW 44 bis KW 12.
    """
    __tablename__ = "work_time_model_validities"
    __table_args__ = (UniqueConstraint("model_id", name="uq_work_time_model_validity_model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("work_time_models.id"), index=True)
    valid_from_week: Mapped[int] = mapped_column(default=1)
    valid_to_week: Mapped[int] = mapped_column(default=53)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkTimeBreakRule(Base):
    """Automatischer Pausenabzug ab einer Brutto-Arbeitsdauer."""
    __tablename__ = "work_time_break_rules"
    __table_args__ = (UniqueConstraint("model_id", "threshold_hours", name="uq_work_time_break_rule_threshold"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("work_time_models.id"), index=True)
    threshold_hours: Mapped[Decimal] = mapped_column(Numeric(9, 4))
    break_minutes: Mapped[int] = mapped_column(default=0)
    sort_order: Mapped[int] = mapped_column(default=100)
    model: Mapped[WorkTimeModel] = relationship(back_populates="break_rules")


class EmployeeWorkTimeModel(Base):
    """Aktuelles Arbeitszeitmodell eines Mitarbeiters."""
    __tablename__ = "employee_work_time_models"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_work_time_model_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("work_time_models.id"), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    model: Mapped[WorkTimeModel] = relationship()


class TimeEntry(Base):
    """Ist-Zeitbuchung eines Mitarbeiters auf Auftrag und optional LV-Position.

    Fahrzeit wird separat gespeichert und standardmäßig nicht gegen die kalkulierten
    produktiven Soll-Stunden gerechnet. Historische Buchungen behalten über
    counts_as_productive ihre damalige fachliche Einordnung.
    """
    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"), nullable=True, index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    entry_type: Mapped[str] = mapped_column(String(40), default="site", index=True)
    counts_as_productive: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    activity: Mapped[str | None] = mapped_column(String(180), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    break_minutes: Mapped[int] = mapped_column(default=0)
    hours: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="manual", index=True)
    status: Mapped[str] = mapped_column(String(30), default="booked", index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee: Mapped["Employee"] = relationship()
    project: Mapped[Project] = relationship()
    order: Mapped[Order] = relationship()
    order_item: Mapped[OrderItem | None] = relationship()



class TimeEntryGroup(Base):
    """Klammer fuer eine Gruppen-Zeitbuchung.

    Die eigentlichen Ist-Zeiten bleiben einzelne TimeEntry-Datensaetze je Mitarbeiter.
    Dadurch bleiben Lohn-/Nachkalkulation und Audit personengenau.
    """
    __tablename__ = "time_entry_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    initiated_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    entry_type: Mapped[str] = mapped_column(String(40), default="site", index=True)
    activity: Mapped[str | None] = mapped_column(String(180), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    break_minutes: Mapped[int] = mapped_column(default=0)
    hours: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="booked", index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TimeEntryGroupMember(Base):
    __tablename__ = "time_entry_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "employee_id", name="uq_time_entry_group_employee"),
        UniqueConstraint("time_entry_id", name="uq_time_entry_group_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("time_entry_groups.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    time_entry_id: Mapped[int] = mapped_column(ForeignKey("time_entries.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GeneralSettings(Base):
    """Zentrale Unternehmens- und Standardstammdaten."""

    __tablename__ = "general_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    company_name: Mapped[str] = mapped_column(String(255), default="DACHKONZEPTE Rödchen GmbH")
    managing_director: Mapped[str | None] = mapped_column(String(255), nullable=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(120), default="Deutschland")
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    vat_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    register_court: Mapped[str | None] = mapped_column(String(160), nullable=True)
    register_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(80), nullable=True)
    bic: Mapped[str | None] = mapped_column(String(40), nullable=True)
    default_vat_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("19.00"))
    default_quote_intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_quote_outro: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Eigenes, dediziertes Sidebar-Logo (seit 1.3.43, siehe CLAUDE.md "Firmenlogo in der
    # Sidebar") -- das Firmenlogo (logo_filename oben) enthält einen Schriftzug ("DACHKONZEPTE
    # GmbH"/"RÖDCHEN"), der in der schmalen Sidebar bei keiner erlaubten Höhe mehr lesbar wäre.
    # Hier lässt sich eine eigene, reduzierte Variante hinterlegen -- app/company_logo.py::
    # sidebar_logo_filename() löst daraus auf, was _sidebar.html tatsächlich zeigt (Sidebar-Logo
    # -> Firmenlogo -> Schriftzug).
    sidebar_logo_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Anzeigehöhe des in der Sidebar gezeigten Logos (seit 1.3.39, Bereich auf 24-120px erweitert
    # und Standardwert von 48 auf 64 angehoben seit 1.3.44, siehe CLAUDE.md "Umgestaltung der
    # Sidebar") -- einstellbar (app/company_logo.py: MIN/MAX_SIDEBAR_LOGO_HEIGHT_PX), damit der
    # Betreiber bei einem Logo mit kleinem Bildzeichen samt Schriftzug nicht bei jedem Wechsel
    # nachfragen muss. Gilt unabhängig davon, ob tatsächlich das Sidebar-Logo oder ersatzweise
    # das Firmenlogo gezeigt wird -- NICHT für die eingeklappte Sidebar, die nutzt eine eigene,
    # feste, kleinere Höhe (siehe _sidebar.html). server_default nötig, siehe Lektion aus 1.0.68
    # (NOT-NULL-Spalte auf bereits bestehender Tabelle).
    sidebar_logo_height_px: Mapped[int] = mapped_column(default=64, server_default="64")
    # Öffentliche Adresse für QR-Codes/Links (seit Betriebsmittelverwaltung Stufe 2) -- optionaler
    # Override, falls die aus der jeweiligen Anfrage abgeleitete Domain (request.base_url) hinter
    # einem Reverse-Proxy nicht das Schema/den Host zeigt, unter dem die Installation öffentlich
    # erreichbar ist. Bleibt das Feld leer, wird request.base_url verwendet -- kein hartkodierter
    # Wert, der sonst bei jeder Installation auf "localhost" zeigen würde.
    public_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Automatisierung im Mahnwesen (seit 1.0.71): legt automatisch einen
    # Mahnungs-ENTWURF an, sobald die nächste Mahnstufe einer Rechnung
    # fällig ist -- versendet wird dadurch nie automatisch, das bleibt
    # immer ein bewusster, manueller Schritt. server_default nötig, siehe
    # Lektion aus 1.0.68 (NOT-NULL-Spalte auf bereits bestehender Tabelle).
    reminders_auto_create_drafts: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # Individualisierbare Akzentfarbe der Oberfläche (Buttons, aktive Navigation,
    # Hervorhebungen) -- Hex-Code, gilt zentral für alle Benutzer. server_default
    # nötig, siehe Lektion aus 1.0.68 (NOT-NULL-Spalte auf bereits bestehender Tabelle).
    accent_color: Mapped[str] = mapped_column(String(20), default="#0d9488", server_default="#0d9488")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NumberSequence(Base):
    """Konfigurierbarer Nummernkreis für Geschäftsobjekte."""

    __tablename__ = "number_sequences"
    __table_args__ = (UniqueConstraint("sequence_key", name="uq_number_sequence_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sequence_key: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str] = mapped_column(String(120))
    format_pattern: Mapped[str] = mapped_column(String(120))
    start_value: Mapped[int] = mapped_column(default=1)
    next_value: Mapped[int] = mapped_column(default=1)
    reset_yearly: Mapped[bool] = mapped_column(Boolean, default=False)
    last_year: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmployeeFunction(Base):
    """In den Einstellungen gepflegte Funktion/Tätigkeit eines Mitarbeiters."""

    __tablename__ = "employee_functions"
    __table_args__ = (UniqueConstraint("name", name="uq_employee_function_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    employee_group: Mapped[str] = mapped_column(String(30), default="gewerblich", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee_profiles: Mapped[list["EmployeeProfile"]] = relationship(back_populates="function")


class Employee(Base):
    """Schlanke Mitarbeiter-Stammdatenbasis für Kalkulation und späteres Personalmodul."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_number: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120), index=True)
    # Legacy-/Kompatibilitätsfeld. Die führende Funktion liegt ab 0.5.3 in EmployeeProfile.
    job_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    employee_group: Mapped[str] = mapped_column(String(30), default="gewerblich", index=True)
    hourly_wage: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    weekly_hours: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("40.00"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile: Mapped["EmployeeProfile | None"] = relationship(
        back_populates="employee", cascade="all, delete-orphan", uselist=False
    )
    compensation: Mapped["EmployeeCompensationSettings | None"] = relationship(
        back_populates="employee", cascade="all, delete-orphan", uselist=False
    )


class EmployeeCompensationSettings(Base):
    """Vergütungsmodell eines Mitarbeiters ohne ALTER TABLE an Bestandsinstallationen.

    hourly_wage im Employee bleibt als kompatibler kalkulatorischer Stundenwert erhalten.
    Bei Festgehalt wird er aus Monatsbrutto, Wochenstunden und Wochen/Jahr abgeleitet.
    """

    __tablename__ = "employee_compensation_settings"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_compensation_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    compensation_type: Mapped[str] = mapped_column(String(30), default="hourly", index=True)
    monthly_salary: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee: Mapped[Employee] = relationship(back_populates="compensation")


class EmployeeCostAllocationSettings(Base):
    """Steuert, wie ein Mitarbeiter in die Verrechnungssatz-Kalkulation einfließt.

    Additive Erweiterung ohne ALTER TABLE: bestehende gewerbliche Mitarbeiter gelten
    ohne Datensatz weiterhin als direkte Lohnkosten, kaufmännische als ausgeschlossen.
    """

    __tablename__ = "employee_cost_allocation_settings"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_cost_allocation_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    allocation_type: Mapped[str] = mapped_column(String(40), default="labor_rate", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmployeeProfile(Base):
    """Erweiterte Mitarbeiter-Stammdaten ohne ALTER TABLE auf bestehenden Installationen."""

    __tablename__ = "employee_profiles"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_profile_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    function_id: Mapped[int | None] = mapped_column(ForeignKey("employee_functions.id"), nullable=True, index=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(120), default="Deutschland")
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    important_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee: Mapped[Employee] = relationship(back_populates="profile")
    function: Mapped[EmployeeFunction | None] = relationship(back_populates="employee_profiles")


class LaborRateSettings(Base):
    """Parameter zur transparenten Ermittlung des Stundenkostenverrechnungssatzes.

    Bewusst eigene Tabelle: Updates von bestehenden Prototyp-Datenbanken benötigen
    dadurch keine invasive ALTER-TABLE-Migration.
    """

    __tablename__ = "labor_rate_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    employer_cost_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("25.00"))
    productive_time_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("70.00"))
    annual_overhead: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    target_profit_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("0"))
    weeks_per_year: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("52.00"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LaborRateOverheadSettings(Base):
    """Fixe und variable Gemeinkosten für den Stundenverrechnungssatz.

    Beide Kostenarten können als Jahresbetrag in EUR oder als Prozentsatz der
    direkten Jahreslohnkosten inkl. Arbeitgebernebenkosten gepflegt werden.
    """

    __tablename__ = "labor_rate_overhead_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    fixed_overhead_mode: Mapped[str] = mapped_column(String(10), default="eur")
    fixed_overhead_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    variable_overhead_mode: Mapped[str] = mapped_column(String(10), default="eur")
    variable_overhead_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductiveHoursSettings(Base):
    """Herleitung von LaborRateSettings.productive_time_pct aus einzelnen Annahmen (seit 1.5.1,
    Verrechnungssatz-Kreislauf Schicht 3, siehe CLAUDE.md "Betriebskosten-Übersicht") -- ersetzt
    keinen bestehenden Mechanismus, calculate_labor_rate() (app/labor_rate.py) liest weiterhin
    ausschließlich LaborRateSettings.productive_time_pct selbst, unverändert.

    weeks_per_year kommt bewusst NICHT hierher, sondern bleibt bei LaborRateSettings -- eine
    Quelle für dieselbe Zahl, kein zweites, eigenes Feld dafür (siehe CLAUDE.md-Lehre aus
    build_customer_and_meta_block()'s drei divergierenden Kopien).

    Schreibt das Ergebnis erst nach einem bewussten Klick
    (app/productive_hours.py::apply_productive_hours_to_labor_rate(), Muster
    apply_labor_rate_calculation()) in productive_time_pct -- kein Automatismus.

    Ist-Werte als Orientierung (seit der Nachbesserung "Ist-Werte im Produktivstunden-Rechner",
    siehe CLAUDE.md): public_holidays bekommt einen errechneten, aber übersteuerbaren Vorschlag
    aus PlanningHoliday; average_sick_days/weather_loss_days bekommen einen aus TimeEntry/
    EmployeeAbsence hergeleiteten Vergleichswert daneben, der NIE geschrieben wird -- keine
    dieser drei Spalten wird durch die Ist-Werte selbst verändert, nur update_productive_hours_
    settings() (der bewusste Speichern-Klick) schreibt sie weiterhin. Siehe
    app/productive_hours.py::weather_days_actual()/sick_days_actual()/public_holidays_suggestion()."""

    __tablename__ = "productive_hours_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    weekly_hours: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("40.00"))
    daily_hours: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("8.00"))
    vacation_days: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("30.00"))
    public_holidays: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("10.00"))
    average_sick_days: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("10.00"))
    weather_loss_days: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("5.00"))
    unproductive_time_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal("15.00"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SettingOptionGroup(Base):
    """Generische, zentral pflegbare Auswahlliste für ERP-Dropdowns."""

    __tablename__ = "setting_option_groups"
    __table_args__ = (UniqueConstraint("group_key", name="uq_setting_option_group_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_key: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    options: Mapped[list["SettingOption"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="SettingOption.sort_order"
    )


class SettingOption(Base):
    """Ein Wert einer generischen Auswahlliste; value ist der fachlich gespeicherte Wert."""

    __tablename__ = "setting_options"
    __table_args__ = (
        UniqueConstraint("group_id", "label", name="uq_setting_option_group_label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("setting_option_groups.id"), index=True)
    label: Mapped[str] = mapped_column(String(180))
    value: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group: Mapped[SettingOptionGroup] = relationship(back_populates="options")


class EmployeeRoleSettings(Base):
    """Zusätzliche Mitarbeiter-Freigaben ohne ALTER TABLE an bestehenden Installationen."""

    __tablename__ = "employee_role_settings"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_role_settings_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    available_as_caseworker: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)




class EmployeePlanningSettings(Base):
    """Steuert, ob ein Mitarbeiter in Plantafel und Kapazitätsplanung sichtbar/berücksichtigt wird."""
    __tablename__ = "employee_planning_settings"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_planning_settings_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    show_on_planning_board: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QuoteEmployeeAssignment(Base):
    """Verknüpft das Angebot mit einem Sachbearbeiter, hält die Quote-Metatabelle migrationsarm."""

    __tablename__ = "quote_employee_assignments"
    __table_args__ = (UniqueConstraint("quote_id", name="uq_quote_employee_assignment_quote"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    caseworker_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppUser(Base):
    """ERP-Benutzer für personengenaues Änderungsprotokoll."""

    __tablename__ = "app_users"
    __table_args__ = (UniqueConstraint("username", name="uq_app_user_username"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(160))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(30), default="user", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Zwei-Faktor-Authentifizierung (TOTP, seit 1.3.34, siehe CLAUDE.md
    # "Zwei-Faktor-Authentifizierung für Administratoren") -- verschlüsselt
    # abgelegt wie das SMTP-Passwort (app/crypto.py::encrypt_secret()), da der
    # Klartext zur Code-Prüfung wiederherstellbar sein muss. totp_confirmed_at
    # bleibt NULL, solange die Einrichtung nicht mit einem echten, von der App
    # gelieferten Code bestätigt wurde -- ein abgebrochener Einrichtungsversuch
    # hinterlässt dadurch nie einen halb aktiven Zustand.
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    recovery_codes: Mapped[list["TwoFactorRecoveryCode"]] = relationship(cascade="all, delete-orphan")
    trusted_devices: Mapped[list["TrustedDevice"]] = relationship(cascade="all, delete-orphan")

    @property
    def two_factor_configured(self) -> bool:
        """Für AppUserOut (schemas.py) -- FastAPI liest response_model-Felder auch über
        Properties, nicht nur über echte Spalten."""
        return self.totp_confirmed_at is not None


class TwoFactorRecoveryCode(Base):
    """Einmal-Wiederherstellungscodes für die Zwei-Faktor-Authentifizierung (seit 1.3.34).

    Werden alle zusammen bei der ersten erfolgreichen Bestätigung des zweiten Faktors erzeugt und
    dem Administrator genau einmal im Klartext angezeigt -- danach nur noch als Hash
    (hash_password()/verify_password(), dieselbe Technik wie beim Benutzerpasswort) gespeichert.
    Ein Code wird beim Verbrauch nicht gelöscht, sondern über used_at markiert, damit die
    ursprüngliche Anzahl nachvollziehbar bleibt."""

    __tablename__ = "two_factor_recovery_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(Text)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrustedDevice(Base):
    """"Diesem Gerät für 30 Tage vertrauen" -- ein vertrautes Gerät muss den zweiten Faktor bis
    zum Ablauf nicht bei jeder Anmeldung erneut vorzeigen (das Passwort bleibt davon unberührt,
    wird weiterhin bei jeder Anmeldung verlangt). Der Token wird wie ein Wiederherstellungscode
    NUR gehasht gespeichert (hash_password()/verify_password(), app/auth.py) -- er wird nie
    zurückgelesen, nur beim Prüfen verglichen; das zugehörige, signierte Cookie (dk_erp_trust,
    app/device_trust.py) trägt die Zeilen-ID plus das rohe Geheimnis.

    Entsteht ausschließlich bei der ROUTINE-Bestätigung des zweiten Faktors
    (POST /api/account/2fa/verify, Häkchen "Diesem Gerät vertrauen"), NIE bei der Ersteinrichtung
    (POST /api/account/2fa/setup/confirm kennt dieses Feld nicht) -- in dem Moment, in dem der
    Schutz gerade erst aufgebaut wird, ihn im selben Schritt für 30 Tage auszusetzen wäre
    widersprüchlich, siehe CLAUDE.md.

    ALLE Zeilen eines Kontos werden gelöscht (app/device_trust.py::revoke_all()), sobald sich der
    zweite Faktor oder das Passwort ändern könnten -- ein zuvor vertrautes Gerät ist danach
    wertlos, der Code wird wieder fällig: bei app/two_factor.py::reset() (Admin-Reset eines
    ANDEREN Kontos UND das Notfallskript scripts/reset_admin_2fa.py, beide rufen dieselbe
    Funktion), bei der eigenen Passwortänderung (app/routers/account.py::change_password()), beim
    admin-gesetzten Passwort eines anderen Benutzers (app/routers/users.py::update_app_user()) und
    beim expliziten Widerruf über "Alle vertrauten Geräte abmelden"."""

    __tablename__ = "trusted_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class FailedLoginAttempt(Base):
    """Persistenter Fehlversuch-Zähler für die Anmeldesperre (seit 1.3.34, ersetzt den
    früheren In-Memory-Zähler in app/auth.py -- siehe CLAUDE.md "Anmeldesicherheit für den
    Onlinebetrieb"). Ein In-Memory-Zähler zählt bei mehreren uvicorn-Workern je Prozess separat
    (aus fünf zulässigen Versuchen würden bei zwei Workern zehn) und ist nach jedem Neustart
    wieder leer -- beides für einen frei aus dem Internet erreichbaren Server ungeeignet.

    Bewusst EINE Zeile pro Fehlversuch (nicht ein Zähler je Schlüssel) -- so bleibt das
    gleitende Zeitfenster ("die letzten N Versuche innerhalb von X Sekunden") exakt nachbildbar,
    ohne den Zeitpunkt jedes einzelnen Versuchs an anderer Stelle mitführen zu müssen.
    `bucket` kodiert sowohl die Art der Sperre als auch den Schlüssel selbst (z. B.
    "login_user:tobias", "login_ip:1.2.3.4", "twofa_user:tobias") -- app/login_security.py ist
    die einzige Stelle, die dieses Format kennt. Alte Zeilen werden bei jedem neuen Fehlversuch
    automatisch mit aufgeräumt (siehe register_failed_attempt()), kein separater Aufräumjob
    nötig -- damit bleibt die Tabelle auf ungefähr die Fehlversuche der letzten Zeitfenster
    begrenzt, unabhängig davon, wie viele Fehlversuche insgesamt je passiert sind."""

    __tablename__ = "failed_login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    bucket: Mapped[str] = mapped_column(String(160), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class UserDashboardWidget(Base):
    """Pro Benutzer gespeichertes Dashboard-Layout (sichtbare Widgets + Reihenfolge).

    Neue Tabelle seit 1.0.102 -- widget_key referenziert einen Eintrag in der
    frontend-seitigen WIDGETS-Registry (dashboard.html), nicht eine eigene
    Datenbanktabelle. Künftige Module registrieren dort einfach weitere Keys."""

    __tablename__ = "user_dashboard_widgets"
    __table_args__ = (UniqueConstraint("user_id", "widget_key", name="uq_user_dashboard_widget"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    widget_key: Mapped[str] = mapped_column(String(60))
    sort_order: Mapped[int] = mapped_column(default=100)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)


class EnabledModule(Base):
    """Ein-/Ausschalter für optionale ERP-Module, pro Installation (seit 1.0.103).

    Fehlt eine Zeile für einen module_key, gilt das Modul als aktiv (Opt-out statt
    Opt-in) -- ein neuer Registry-Eintrag ändert dadurch nie stillschweigend etwas an
    einer bestehenden Installation. Die Kern-ERP-Kette (Kunde/Projekt/Angebot/Auftrag/
    Rechnung/Mahnung, Zeiterfassung, Planung) taucht hier bewusst nicht auf -- nur
    echte, optionale Module wie Aufgabenmanagement (siehe app/modules.py, OPTIONAL_MODULES)."""

    __tablename__ = "enabled_modules"
    __table_args__ = (UniqueConstraint("module_key", name="uq_enabled_module_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    module_key: Mapped[str] = mapped_column(String(60))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(Base):
    """Freie, eigenständige Aufgabe (seit 1.1.0, Modul "aufgabenmanagement") --
    unabhängig von den auftragsgebundenen WorkPreparationTask-Zeilen. Kann optional an
    ein Projekt gehängt werden, muss aber nicht.

    source_module/source_label/source_url sind die Automatisierungs-Anschlussstelle für
    künftige Module (z. B. digitale Wartungsberichte, die automatisch eine
    Rechnungs-Aufgabe für den zuständigen Sachbearbeiter anlegen wollen): bewusst drei
    freie Felder statt einer polymorphen FK-Beziehung, damit ein neues auslösendes
    Modul hier andocken kann, ohne dass tasks selbst geändert werden muss. NULL/leer bei
    manuell über die Seite angelegten Aufgaben."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="offen", index=True)
    priority: Mapped[str] = mapped_column(String(30), default="normal")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Archivieren (seit 1.2.10) -- rein informatives Ausblenden aus dem Standard-Board,
    # jederzeit umkehrbar, gleiches Muster wie Project.archived. Echtes Löschen bleibt
    # zusätzlich möglich.
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)

    source_module: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Rollen-Zielgruppe für empfängerlose Aufgaben (seit 1.5.0) -- allgemeine Erweiterung des
    # claim/release-Modells (1.4.3), nicht nur für Betriebskosten. NULL = wie bisher an jedes
    # Büro-/Admin-Konto (list_tasks_for_user()); z. B. "buero_finanzen" grenzt eine
    # empfängerlose Aufgabe auf Finanzen+Admin ein (ROLE_RANK-Hierarchie, has_min_role()) -- ein
    # buero_auftrag-Konto sieht/übernimmt sie dann nicht. Wirkt NUR auf empfängerlose Aufgaben;
    # eine bereits zugewiesene Aufgabe ignoriert dieses Feld, die Zuweisung selbst entscheidet.
    min_visible_role: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)

    assigned_employee: Mapped["Employee | None"] = relationship()
    project: Mapped["Project | None"] = relationship()
    checklist_items: Mapped[list["TaskChecklistItem"]] = relationship(
        cascade="all, delete-orphan", order_by="TaskChecklistItem.sort_order, TaskChecklistItem.id"
    )


class TaskColumn(Base):
    """Konfigurierbare Kanban-Spalte für Aufgaben (seit 1.1.1) -- ersetzt die zuvor drei fest
    kodierten Status offen/in_arbeit/erledigt durch eine vom Admin frei erweiterbare, umbenenn-
    und sortierbare Liste. Task.status referenziert `key` (stabiler String), nicht die
    numerische id, damit ein Umbenennen (label) bestehende Aufgaben nicht verwaist."""

    __tablename__ = "task_columns"
    __table_args__ = (UniqueConstraint("key", name="uq_task_column_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(default=0)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaskChecklistItem(Base):
    """Abhakbarer Unterpunkt einer Aufgabe (seit 1.1.2), um sie strukturiert abzuarbeiten."""

    __tablename__ = "task_checklist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaskSettings(Base):
    """Einstellungen für das Aufgabenmanagement-Modul (seit 1.1.3), Singleton wie
    LaborRateSettings (immer genau eine Zeile mit id=1)."""

    __tablename__ = "task_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    notify_on_assignment: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MobileSettings(Base):
    """Einstellungen für die Monteursansicht (seit 1.3.0), Singleton wie TaskSettings/
    MaintenanceSettings (immer genau eine Zeile mit id=1). shift_end_time ist der einzige
    Zweck dieser Tabelle: eine feste Uhrzeit, ab der die Fahrzeug-Tablet-Anmeldung als beendet
    gilt (siehe is_past_shift_end() in app/mobile_settings.py) -- geprüft nur an den mobilen
    Einstiegspunkten (GET /mobil, GET /api/field-view/today -- /mobil hieß bis 1.3.60 /vor-ort), NICHT in der globalen
    Middleware, damit Schreibtisch-Nutzer mit demselben Login-Mechanismus davon unberührt
    bleiben."""

    __tablename__ = "mobile_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    shift_end_time: Mapped[dt_time] = mapped_column(Time, default=dt_time(19, 0), server_default="19:00:00")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MaintenanceContract(Base):
    """Wiederkehrender Wartungsvertrag (seit 1.2.0, Modul "wartungen") -- erinnert zum
    Fälligkeitstermin (siehe check_due_contracts_and_create_reminders() in
    app/maintenance_contracts.py) über eine normale Aufgabe an den zuständigen Mitarbeiter,
    löst aber NIE selbständig einen neuen Vorgang aus (bewusst kein Scheduler, siehe CLAUDE.md
    -- ein Sachbearbeiter prüft und klickt bewusst). property_id (seit 1.2.9 optional, siehe
    CLAUDE.md) verweist auf ein zusätzliches "Objekt" des Kunden -- ohne Auswahl gilt die
    Hauptadresse des Kunden selbst als Einsatzort (contract_to_dict() in
    app/maintenance_contracts.py bildet diesen Rückfall nach). last_reminder_due_date ist der
    Idempotenz-Stempel, der verhindert, dass ein erneuter Seitenaufruf für denselben
    Fälligkeitszyklus ein zweites Mal erinnert.

    Positionen je Dachfläche (MaintenanceContractItem, seit 1.2.15): sobald ein Vertrag
    mindestens eine aktive (nicht archivierte) Position hat, lösen next_due_date/
    interval_months auf DIESER Klasse für Fälligkeit/Erinnerung/"Vorgang erstellen" NICHT mehr
    aus -- ausschließlich die Positionsebene entscheidet dann (siehe _is_due() in
    app/maintenance_contracts.py). Beide Spalten bleiben unangetastet für Verträge ohne
    Positionen sowie als Rückfall, falls alle Positionen wieder archiviert werden."""

    __tablename__ = "maintenance_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    interval_months: Mapped[int] = mapped_column(default=12)
    next_due_date: Mapped[date] = mapped_column(Date)
    last_reminder_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    template_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    responsible_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="aktiv", server_default="aktiv")
    # Archivieren (seit 1.2.10) -- rein informatives Ausblenden aus der Standardliste,
    # jederzeit umkehrbar, unabhängig von status (aktiv/pausiert/beendet). Gleiches Muster
    # wie Project.archived. Echtes Löschen (delete_contract()) bleibt zusätzlich möglich.
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer: Mapped["Customer"] = relationship()
    property: Mapped["Property | None"] = relationship()
    template_project: Mapped["Project | None"] = relationship()
    responsible_employee: Mapped["Employee | None"] = relationship()
    items: Mapped[list["MaintenanceContractItem"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", order_by="MaintenanceContractItem.id"
    )


class MaintenanceSettings(Base):
    """Einstellungen für das Modul "wartungen" (seit 1.2.6), Singleton wie LaborRateSettings/
    TaskSettings (immer genau eine Zeile mit id=1). reminder_lead_days steuert, ab wie vielen
    Tagen VOR next_due_date ein Wartungsvertrag bereits als fällig gilt (contract_to_dict()
    in app/maintenance_contracts.py) -- vorher galt nur "next_due_date <= heute" (rein
    überfällig, keine Vorlaufzeit), was dazu führte, dass ein erst in wenigen Tagen fälliger
    Vertrag nirgends auftauchte. default_responsible_employee_id ist der Rückfall, wenn ein
    einzelner Vertrag keinen eigenen responsible_employee_id trägt.

    use_roof_area_items (seit 1.2.19, Default False): steuert, ob "Zu wartende Dachflächen"
    (MaintenanceContractItem, seit 1.2.15 "Positionen" genannt) in der Oberfläche überhaupt
    erscheinen und ob sie die Fälligkeitssteuerung von der Vertragsebene übernehmen. Ist der
    Schalter aus, verhält sich JEDER Vertrag ausschließlich über next_due_date/interval_months,
    auch wenn er noch Altbestand-Positionen aus einer Zeit trägt, in der der Schalter an war --
    diese Zeilen bleiben in der DB, werden aber weder angezeigt noch für Fälligkeit/Erinnerung
    ausgewertet (siehe app/maintenance_contracts.py: _is_due(),
    check_due_contracts_and_create_reminders(), create_project_from_contract())."""

    __tablename__ = "maintenance_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    reminder_lead_days: Mapped[int] = mapped_column(default=30, server_default="30")
    use_roof_area_items: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    default_responsible_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    default_responsible_employee: Mapped["Employee | None"] = relationship()


class ServiceReport(Base):
    """Digitaler Einsatzbericht (seit 1.2.1, Modul "wartungen") -- Rapportbericht bei
    Reparaturen, Wartungsbericht bei Wartungen. Hängt bewusst am Order (nicht am
    MaintenanceContract), da auch spontane Reparaturen ohne Wartungsvertrag Berichte
    brauchen. Die zugehörigen Zeitbuchungen werden NICHT per eigener FK-Spalte an TimeEntry
    verknüpft -- Order verbindet beide bereits, GET /api/time-entries?order_id=... liefert die
    relevanten Buchungen direkt.

    Unveränderlich nach der Unterschrift (status="unterschrieben"), gleiches Muster wie
    Invoice/Order/Reminder. Erst die Unterschrift (sign_service_report() in
    app/service_reports.py) löst die "Rechnung erstellen"-Aufgabe für
    Order.caseworker_employee_id aus -- der erste echte Aufrufer der Automatisierungs-
    Anschlussstelle außerhalb der Wartungsverträge.

    maintenance_contract_id/maintenance_contract_item_id (seit 1.2.15, beide optional) werden
    von create_report() automatisch aus order.project.profile übernommen, sofern der Auftrag
    über create_project_from_contract() entstanden ist -- ein einmaliger Schnappschuss beim
    Anlegen, keine live nachgezogene Beziehung. Ermöglicht list_contract_history() in
    app/service_reports.py, ohne Order selbst um einen Vertragsbezug zu erweitern.

    roof_area_id/inspection_template_id/inspection_template_version (seit 1.2.16) waren der
    Auflösungs-Schnappschuss für die strukturierten Prüfpunkte (InspectionItem), als ein Bericht
    noch an genau einer Dachfläche hing. Seit 1.2.22 (mehrere Dachflächen je Bericht, siehe
    ServiceReportRoofArea) schreibt create_report() diese drei Spalten für NEUE Berichte nicht
    mehr -- sie bleiben nur zur Anzeige/Auswertung bestehender, vor 1.2.22 angelegter Berichte
    erhalten (nie verworfene Daten, gleiches Prinzip wie RoofArea.build_up). report_roof_areas
    ist die alleinige, verlässliche Quelle dafür, welche Dachflächen an einem NEUEN Bericht
    beteiligt waren -- unabhängig davon, ob die aufgelöste Vorlage für eine Fläche überhaupt
    Prüfpunkte erzeugt hat.

    advance_due_date_on_sign (seit 1.2.22): nur von create_maintenance_visit() ("Wartung
    durchführen" auf der Vertragsseite) gesetzt -- sign_report() schreibt dann bei der
    Unterschrift (nicht beim Anlegen!) die Fälligkeit des verknüpften MaintenanceContract fort.
    Ein abgebrochener/gelöschter Entwurf verschiebt den Turnus dadurch nicht. Der bestehende Weg
    "Vorgang erstellen" (create_project_from_contract()) schreibt die Fälligkeit weiterhin beim
    Anlegen fort und setzt dieses Feld nie -- beide Wege bleiben unabhängig, keine doppelte
    Fortschreibung.

    installer_signature_path/-name/-signed_at (seit 1.3.0, Monteursansicht): zweite,
    eigenständige Unterschrift -- signature_path/-name/signed_at bleiben unverändert die des
    KUNDEN (nicht umbenannt, um bestehende Referenzen/Daten nicht anzufassen), die neuen Spalten
    sind exakt parallel dazu für den MONTEUR. Beide nullable: ein vor 1.3.0 unterschriebener
    Bericht hat nur die Kunden-Unterschrift, die installer_*-Spalten bleiben NULL und werden im
    PDF/UI entsprechend ausgelassen statt eine leere zweite Spalte zu erzwingen. sign_report()
    verlangt für NEUE Unterschriften ab 1.3.0 beide auf einmal (keine eigene Tabelle -- die
    Kardinalität ist fix zwei, ein generischer Unterschriften-Join wäre eine Abstraktion ohne
    Gegenwert für einen Fall, der nie über zwei hinauswächst)."""

    __tablename__ = "service_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(30))  # rapport|wartung
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    performed_at: Mapped[date] = mapped_column(Date, default=date.today)
    signature_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signature_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    installer_signature_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    installer_signature_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    installer_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="entwurf", server_default="entwurf")
    maintenance_contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_contracts.id"), nullable=True, index=True
    )
    maintenance_contract_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_contract_items.id"), nullable=True, index=True
    )
    roof_area_id: Mapped[int | None] = mapped_column(ForeignKey("roof_areas.id"), nullable=True, index=True)
    inspection_template_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_templates.id"), nullable=True)
    inspection_template_version: Mapped[int | None] = mapped_column(nullable=True)
    advance_due_date_on_sign: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order: Mapped["Order"] = relationship()
    created_by_employee: Mapped["Employee | None"] = relationship()
    maintenance_contract: Mapped["MaintenanceContract | None"] = relationship()
    maintenance_contract_item: Mapped["MaintenanceContractItem | None"] = relationship()
    roof_area: Mapped["RoofArea | None"] = relationship()
    inspection_template: Mapped["InspectionTemplate | None"] = relationship()
    report_roof_areas: Mapped[list["ServiceReportRoofArea"]] = relationship(
        cascade="all, delete-orphan", order_by="ServiceReportRoofArea.id"
    )
    inspection_items: Mapped[list["InspectionItem"]] = relationship(
        cascade="all, delete-orphan", order_by="InspectionItem.sort_order, InspectionItem.id"
    )
    findings: Mapped[list["Finding"]] = relationship(back_populates="service_report", cascade="all, delete-orphan")
    photos: Mapped[list["ServiceReportPhoto"]] = relationship(cascade="all, delete-orphan")
    materials: Mapped[list["ServiceReportMaterial"]] = relationship(
        cascade="all, delete-orphan", order_by="ServiceReportMaterial.sort_order, ServiceReportMaterial.id"
    )
    assets: Mapped[list["ServiceReportAsset"]] = relationship(
        cascade="all, delete-orphan", order_by="ServiceReportAsset.sort_order, ServiceReportAsset.id"
    )


class ServiceReportRoofArea(Base):
    """Eine an einem ServiceReport beteiligte Dachfläche (seit 1.2.22, Mehrflächen-Berichte) --
    ein Objekt mit mehreren Dachflächen bekommt einen einzigen Bericht mit einer einzigen
    Unterschrift statt eines Berichts je Fläche. Trägt den je Fläche EIGENEN
    Vorlagen-Schnappschuss (verschiedene Flächen eines Berichts können unterschiedliche
    Dachtypen und damit unterschiedliche InspectionTemplate haben) -- das ersetzt die früher
    einzelne, jetzt nur noch für Altbestand gepflegte Schnappschuss-Spalte am ServiceReport
    selbst (siehe dessen Docstring). Ist zugleich die alleinige Quelle dafür, welche Flächen an
    einem Bericht beteiligt waren, auch wenn die aufgelöste Vorlage für eine Fläche keine
    Prüfpunkte erzeugt hat (inspection_template_id dann NULL).

    inspection_template_label_snapshot (seit 1.3.22) friert zusätzlich die Vorlagenbezeichnung
    zum Anlagezeitpunkt ein -- letzter loser Faden einer sonst bereits vollständig eingefrorenen
    Kette (RoofArea-Name, RoofComponent-Name, InspectionItem.text, Vorlagenversion), siehe CLAUDE.md
    "Eingefrorene Bauteil-/Dachflächennamen"/„Bekannte, bewusst offene Punkte" (1.3.12-Fund).

    Echte, neue Tabelle mit Cascade (ServiceReport.report_roof_areas) -- kein Regel-6-Fall wie
    die migrationsarmen Zusatztabellen zu bestehenden Kern-Tabellen."""

    __tablename__ = "service_report_roof_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_report_id: Mapped[int] = mapped_column(ForeignKey("service_reports.id"), index=True)
    roof_area_id: Mapped[int] = mapped_column(ForeignKey("roof_areas.id"), index=True)
    # Physischer Namens-Schnappschuss (seit 1.3.12) -- dieselbe Begründung wie
    # Finding.roof_component_name_snapshot: RoofArea.name kann sich nach der Unterschrift durch
    # eine Umbenennung ändern, roof_area_id selbst bleibt der reine FK. Nullable, Bestandszeilen
    # werden in der Migration aus dem heutigen Namen befüllt statt leer gelassen.
    roof_area_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inspection_template_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_templates.id"), nullable=True)
    inspection_template_version: Mapped[int | None] = mapped_column(nullable=True)
    # Physischer Namens-Schnappschuss (seit 1.3.22) -- dieselbe Begründung wie
    # roof_area_name_snapshot oben: InspectionTemplate.label kann sich nach der Unterschrift durch
    # eine Umbenennung (update_template()) ändern, inspection_template_id selbst bleibt der reine
    # FK. Nullable, NULL wenn kein Template aufgelöst wurde (siehe inspection_template_id
    # oben) -- Bestandszeilen werden in der Migration aus dem heutigen Namen befüllt.
    inspection_template_label_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    roof_area: Mapped["RoofArea"] = relationship()
    inspection_template: Mapped["InspectionTemplate | None"] = relationship()


class AuditLog(Base):
    """Unveränderliches fachliches Änderungsprotokoll."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    actor_name: Mapped[str] = mapped_column(String(160), default="System", index=True)
    action: Mapped[str] = mapped_column(String(30), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entity_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    field_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    field_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_method: Mapped[str | None] = mapped_column(String(12), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentLayoutBlock(Base):
    """Ein gezeichneter Rahmen-Baustein des gemeinsamen PDF-Rahmens (seit 1.0.58, ursprünglich für
    den positionsbasierten Angebots-Layout-Editor; dieser und sein content-tragender
    custom_text-Baustein sind beim Aufräumen nach dem PDF-Umbau in 1.3.20 entfernt worden, siehe
    CLAUDE.md "Gemeinsamer Dokumenttyp").

    Jeder Block hat eine feste Position/Größe in Millimetern auf der Seite
    (A4 = 210 x 297 mm, Ursprung oben links -- x wächst nach rechts, y wächst
    nach unten, das ist gebräuchlicher für Seitenlayout als reportlabs
    eigenes PDF-Koordinatensystem, das von unten links aus zählt; die
    Umrechnung passiert erst beim tatsächlichen Zeichnen).

    Seit 1.3.20 nur noch vier block_type-Werte in Gebrauch (FRAME_BLOCK_TYPES,
    app/document_frame.py): logo, company_header, footer_text, continuation_header -- der
    optionale, gezeichnete Rückfall neben Briefpapier-Hintergrund + Rändern (app/document_frame.py).
    `content` bleibt für alle vier leer, ihr Inhalt kommt aus den echten Einstellungen
    (GeneralSettings) bzw. wird zur Laufzeit berechnet (Seitenzahl, Wiederholungszeilen-Werte).

    document_type ist von Anfang an vorgesehen (nicht erst später nachgerüstet) -- seit 1.3.6
    teilen sich alle Dokumenttypen außer eigenen Sonderfällen denselben, unter
    document_type='default' abgelegten Satz (siehe app/document_type_fallback.py)."""

    __tablename__ = "document_layout_blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(20), index=True)  # 'quote' | 'order' | 'invoice' | 'reminder'
    block_type: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(120))
    x_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    y_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    width_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    height_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    font_size: Mapped[Decimal] = mapped_column(Numeric(4, 1), default=Decimal("9.5"))
    font_weight: Mapped[str] = mapped_column(String(10), default="normal")  # 'normal' | 'bold'
    text_align: Mapped[str] = mapped_column(String(10), default="left")  # 'left' | 'center' | 'right'
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentLayoutBackground(Base):
    """Hintergrundbild (z.B. vorgedruckter Briefbogen) für einen
    Dokumenttyp im PDF-Layout-Editor (seit 1.0.61).

    Wird beim Rendern als volle Seite hinter allen Bausteinen gezeichnet --
    Betriebe mit fertig gestaltetem Briefbogen (Logo, Fußzeile, ggf.
    Dekorelemente bereits enthalten) können diesen direkt hinterlegen,
    statt Logo/Fußzeile aus einzelnen Bausteinen nachzubauen; die
    vorhandenen Sichtbarkeits-Schalter auf logo/footer_text erlauben es,
    diese dann einfach auszublenden, da der Briefbogen sie bereits zeigt.

    Ein Hintergrund pro (document_type, page_type) -- analog zum einen Firmenlogo in
    GeneralSettings, nur mit einer zweiten Achse. Die Datei selbst liegt im eigenen
    Speicherordner, siehe app/document_layout_background.py.

    page_type (seit 1.3.1, Muster wie DocumentPageMargins.page_type): 'first' (Seite 1) oder
    'continuation' (Folgeseiten) -- ein Betrieb kann für ein mehrseitiges Dokument
    unterschiedliches Briefpapier je Seitentyp hinterlegen (z. B. Adressfenster nur auf Seite 1).
    server_default='first' setzt beim Migrieren bestehende Zeilen (bisher genau eine je
    document_type, z. B. das Angebot) automatisch auf 'first' -- unveränderte Bedeutung für
    bestehende Aufrufer, die page_type nicht angeben (siehe get_background() in
    app/document_layout.py). repeat_on_every_page bleibt nur für diesen Altbestandsfall
    (Angebot, ein einzelner Hintergrund) relevant; bei getrennten Seitentyp-Hintergründen (neu
    seit 1.3.1, siehe app/document_frame.py) übernimmt die bloße Existenz der
    'continuation'-Zeile dieselbe Rolle, ein zusätzliches Flag wäre dort redundant.

    repeat_on_every_page (seit 1.0.67): steuert, ob der (einzelne, 'first') Hintergrund bei
    mehrseitigen Dokumenten auf jeder Seite erscheint oder nur auf der ersten -- bewusst als
    Einstellung statt fester Regel, da beide Varianten je nach vorgedrucktem Papierbestand
    sinnvoll sein können."""

    __tablename__ = "document_layout_backgrounds"
    __table_args__ = (UniqueConstraint("document_type", "page_type", name="uq_document_layout_background_type_page"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(20), index=True)
    page_type: Mapped[str] = mapped_column(String(20), default="first", server_default="first")
    stored_filename: Mapped[str] = mapped_column(String(255))
    repeat_on_every_page: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentPageMargins(Base):
    """Feste Randabstände je Seitentyp (seit 1.0.69) -- ergänzt die bisher
    im Code fest verdrahteten Werte (PAGE_BOTTOM_MARGIN_MM,
    CONTINUATION_CONTENT_START_MM in app/quote_layout_pdf.py) um eine
    editierbare Einstellung.

    Separat für page_type='first' (Seite 1) und 'continuation'
    (Folgeseiten), da beide unterschiedliche Anforderungen haben können --
    z.B. mehr oberer Rand auf Seite 1 durch den Firmenkopf, dafür ein
    schlankerer Rand auf Folgeseiten, die nur die schlichte
    Fortsetzungs-Kopfzeile tragen.

    top_mm/bottom_mm steuern direkt die Seitenumbruch-Grenzen der
    Positionsliste (siehe _draw_items_table_paginated). left_mm/right_mm
    positionieren zusätzlich die Fortsetzungs-Kopfzeile und werden im
    Layout-Editor als Hilfslinie eingeblendet -- sie schränken bestehende
    Bausteinpositionen aber bewusst nicht automatisch ein, da die freie
    Positionierung einzelner Bausteine ein zentrales Merkmal des Editors
    bleibt."""

    __tablename__ = "document_page_margins"
    __table_args__ = (UniqueConstraint("document_type", "page_type", name="uq_document_page_margins"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(20), index=True)
    page_type: Mapped[str] = mapped_column(String(20))  # 'first' | 'continuation'
    top_mm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    bottom_mm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    left_mm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    right_mm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SmtpSettings(Base):
    """E-Mail-Versand-Konfiguration (seit 1.0.74, um Microsoft 365/OAuth 2.0
    seit 1.0.79 erweitert -- Tabellenname aus historischen Gründen weiterhin
    'smtp_settings', deckt inzwischen beide Versandwege ab).

    Bewusst allgemein gehalten, nicht auf das Mahnwesen beschränkt -- soll
    künftig für alle Vorgänge (Angebot/Auftrag/Rechnung/Mahnung) dieselbe,
    einmal hinterlegte Konfiguration verwenden. Ein gemeinsames
    Firmenpostfach ergibt fachlich mehr Sinn als je Benutzer eigene
    Zugangsdaten, daher als Singleton wie GeneralSettings.

    send_method wählt zwischen zwei grundsätzlich verschiedenen Versandwegen
    (Klärung: "zusätzlich als wählbare Alternative"):
    - 'smtp': klassisches SMTP mit Benutzername/Passwort (host/port/username/
      password_encrypted/encryption/sender_email/sender_name)
    - 'graph_oauth2': Microsoft Graph API mit OAuth 2.0 Client-Credentials-Flow
      (graph_*-Felder) -- für Microsoft 365/Exchange Online, wo SMTP AUTH
      zunehmend deaktiviert ist. Nutzt eine App-Registrierung in Azure AD mit
      Mail.Send als Application-Berechtigung (nicht Delegated), damit ohne
      interaktive Anmeldung im Hintergrund versendet werden kann.

    password_encrypted/graph_client_secret_encrypted liegen NIE im Klartext
    in der Datenbank -- siehe app/crypto.py (encrypt_secret/decrypt_secret),
    abgeleitet vom bereits bestehenden secret_key() aus app/auth.py. Nur für
    Administratoren einsehbar/änderbar (siehe app/routers/email_settings.py),
    und werden auch beim Bearbeiten nie entschlüsselt an die Oberfläche
    zurückgegeben -- wichtig, sobald mehrere Personen Zugriff auf das ERP
    haben.
    """

    __tablename__ = "smtp_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    send_method: Mapped[str] = mapped_column(String(20), default="smtp", server_default="smtp")  # 'smtp' | 'graph_oauth2'
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int] = mapped_column(default=587)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    encryption: Mapped[str] = mapped_column(String(20), default="starttls")  # 'starttls' | 'ssl' | 'none'
    sender_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Microsoft Graph / OAuth 2.0 (seit 1.0.79)
    graph_tenant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    graph_client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    graph_client_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    graph_sender_mailbox: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentEmailTemplate(Base):
    """E-Mail-Betreff/-Text-Vorlage je Dokumenttyp (seit 1.0.82).

    Analog zu ReminderLevel.email_subject_template/email_body_template,
    aber für Dokumenttypen ohne Stufen-Konzept -- Angebot/Auftrag/Rechnung
    haben (anders als Mahnungen) keine 1./2./3. Stufe, daher genau eine
    Vorlage je Dokumenttyp statt mehrerer.

    NULL bedeutet "noch nicht angepasst" -- die jeweilige Versandfunktion
    (siehe send_quote_email/send_order_email/send_invoice_email) nutzt dann
    einen eingebauten Standardtext, damit der Versand auch ohne manuelle
    Anpassung sofort funktioniert."""

    __tablename__ = "document_email_templates"
    __table_args__ = (UniqueConstraint("document_type", name="uq_document_email_template_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(20), index=True)  # 'quote' | 'order' | 'invoice'
    subject_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RoofArea(Base):
    """Einzelne Dachfläche eines Objekts (seit 1.2.14) -- ein Dachdeckerbetrieb wartet nicht
    "ein Objekt", sondern einzelne Dachflächen mit eigenen Bauteilen (RoofComponent). Erst auf
    Bauteil-Ebene werden spätere Prüfpunkte/Mängel/Historie fachlich sinnvoll ("Gully Nordost,
    dritte Verstopfung in zwei Jahren" statt "Dach hat Probleme").

    build_up/insulation (seit 1.2.18 NUR NOCH HISTORISCH): ursprünglich freier Text für den
    Dachaufbau, seit 1.2.18 durch die strukturierte Schichtenliste (RoofLayer) abgelöst. Die
    Spalten werden NICHT gelöscht (Altbestand geht sonst verloren) und bleiben in
    roof_area_to_dict() lesbar, aber kein Code-Pfad (create_roof_area()/update_roof_area())
    schreibt sie noch -- die Oberfläche zeigt sie nur noch schreibgeschützt als "Aufbau
    (Altbestand, Freitext)", wenn befüllt."""

    __tablename__ = "roof_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    roof_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    covering: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pitch_degrees: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    build_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    insulation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_renovation: Mapped[date | None] = mapped_column(Date, nullable=True)
    contractor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    warranty_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    sketch_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    property: Mapped["Property"] = relationship(back_populates="roof_areas")
    components: Mapped[list["RoofComponent"]] = relationship(
        back_populates="roof_area", cascade="all, delete-orphan",
        order_by="RoofComponent.sort_order, RoofComponent.id",
    )
    # Kein order_by hier: die Anzeigereihenfolge richtet sich nach RoofLayerType.sort_order
    # (einer anderen Tabelle) -- Sortierung passiert ausschließlich auf Dict-Ebene in
    # list_roof_layers() (app/roof_areas.py).
    layers: Mapped[list["RoofLayer"]] = relationship(cascade="all, delete-orphan")


class RoofComponent(Base):
    """Einzelnes Bauteil einer Dachfläche (seit 1.2.14) -- rein neuer Tabellenbaum unterhalb
    von RoofArea, deshalb echte Relationship mit cascade statt migrationsarmem Sonderweg (Regel
    6 gilt hier nicht, da keine bestehende Kerntabelle per ALTER TABLE erweitert wird). sort_order
    (nicht die id) bestimmt die Reihenfolge, da aus dem Bauteilbestand später Prüfpunkte einer
    vom Monteur in fester Reihenfolge abzuarbeitenden Checkliste entstehen sollen."""

    __tablename__ = "roof_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    roof_area_id: Mapped[int] = mapped_column(ForeignKey("roof_areas.id"), index=True)
    component_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    year_built: Mapped[int | None] = mapped_column(nullable=True)
    sketch_x: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sketch_y: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sketch_w: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sketch_h: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=100)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roof_area: Mapped["RoofArea"] = relationship(back_populates="components")


class RoofComponentType(Base):
    """Bauteilart (seit 1.2.19) -- vorher eine reine SettingOptionGroup ("roof_component_types"),
    zur echten Tabelle nach dem Muster von RoofLayerType (1.2.18) hochgestuft, damit is_area
    (flächige vs. punktförmige Markierung auf der Skizze, z. B. Photovoltaik-Felder) an der
    Bauteilart selbst hängt statt inkonsistent am einzelnen RoofComponent. key bleibt bewusst
    textidentisch zu den bisherigen Options-Werten ("Gully", "Photovoltaik", ...), damit
    RoofComponent.component_type/InspectionTemplateItem.component_type (beide einfache Strings,
    kein FK -- exakt wie RoofArea.roof_type schon heute) unverändert weiter funktionieren."""

    __tablename__ = "roof_component_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    label: Mapped[str] = mapped_column(String(120))
    is_area: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MaintenanceWindow(Base):
    """Saisonales Wartungsfenster (seit 1.2.15, Modul "wartungen") -- z. B. "Frühjahr" (März-Mai),
    "Herbst" (Oktober-November). month_to < month_from ist erlaubt (Fenster über den
    Jahreswechsel, z. B. Dezember-Februar). month_from ist der Ankermonat für die jährliche
    Wiederkehr (_next_window_opening() in app/maintenance_contracts.py), month_to bestimmt
    zusammen mit month_from, wann eine fällige Position als "überfällig" gilt
    (_window_close_date()/_is_item_overdue())."""

    __tablename__ = "maintenance_windows"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    month_from: Mapped[int] = mapped_column()
    month_to: Mapped[int] = mapped_column()
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MaintenanceContractItem(Base):
    """Position je Dachfläche innerhalb eines Wartungsvertrags (seit 1.2.15) -- rein neuer
    Tabellenbaum unterhalb von MaintenanceContract, deshalb echte Relationship mit Cascade
    (Regel 6 aus CLAUDE.md gilt hier nicht, keine bestehende Kerntabelle wird per ALTER TABLE
    erweitert). Sobald ein Vertrag mindestens eine aktive (nicht archivierte) Position hat,
    steuert ausschließlich die Positionsebene Fälligkeit/Erinnerung -- siehe
    MaintenanceContract.next_due_date/interval_months. template_project_id ist optional und
    geht dem Vertrags-Mustervorgang (MaintenanceContract.template_project_id) vor, da
    unterschiedliche Positionen unterschiedliche Mustervorgänge brauchen können (z. B.
    Flachdachwartung vs. Rinnenreinigung)."""

    __tablename__ = "maintenance_contract_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("maintenance_contracts.id"), index=True)
    roof_area_id: Mapped[int] = mapped_column(ForeignKey("roof_areas.id"), index=True)
    maintenance_window_id: Mapped[int] = mapped_column(ForeignKey("maintenance_windows.id"), index=True)
    template_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    inspection_template_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_templates.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    next_due_date: Mapped[date] = mapped_column(Date)
    last_reminder_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract: Mapped["MaintenanceContract"] = relationship(back_populates="items")
    roof_area: Mapped["RoofArea"] = relationship()
    maintenance_window: Mapped["MaintenanceWindow"] = relationship()
    template_project: Mapped["Project | None"] = relationship()
    inspection_template: Mapped["InspectionTemplate | None"] = relationship()


class InspectionTemplate(Base):
    """Prüfvorlage je Dachtyp (seit 1.2.16, Modul "wartungen") -- beschreibt, was je Bauteilart
    bei einer Wartung zu prüfen ist. Wird beim Anlegen eines Wartungsberichts gegen den
    tatsächlichen Bauteilbestand der betroffenen Dachfläche "multipliziert"
    (_generate_inspection_items() in app/service_reports.py) und liefert so die konkreten
    InspectionItem-Zeilen des Berichts -- die Vorlage selbst bleibt danach frei bearbeitbar,
    da alles Relevante physisch in den Bericht kopiert wird. version wird bei jedem
    inhaltlichen Speichern (Metadaten oder Punkte, siehe app/inspection_templates.py) um eins
    erhöht -- der Schnappschuss-Stempel, gegen welchen Stand ein Bericht generiert wurde
    (ServiceReport.inspection_template_version)."""

    __tablename__ = "inspection_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(160))
    roof_type: Mapped[str | None] = mapped_column(String(80), nullable=True)  # NULL = gilt für jeden Dachtyp
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["InspectionTemplateItem"]] = relationship(
        back_populates="template", cascade="all, delete-orphan",
        order_by="InspectionTemplateItem.sort_order, InspectionTemplateItem.id",
    )


class RoofTypeInspectionTemplateDefault(Base):
    """Explizite Zuordnung "je Dachtyp genau eine Standardvorlage" (seit 1.2.22) --
    ersetzt in _resolve_inspection_template() die bisherige implizite Auflösung über den
    niedrigsten InspectionTemplate.sort_order, wenn mehrere Vorlagen denselben roof_type tragen.
    roof_type ist absichtlich ein freier String (wie überall in diesem Bereich, siehe
    RoofArea.roof_type) statt eines FK auf eine eigene Dachtyp-Tabelle, passend zur Optionsgruppe
    "roof_types". Eine fehlende Zeile für einen Dachtyp bedeutet "noch keine Standardvorlage
    zugeordnet" -- _resolve_inspection_template() fällt dann auf die vierte Stufe (roof_type IS
    NULL) zurück, kein Fehler."""

    __tablename__ = "roof_type_inspection_template_defaults"

    id: Mapped[int] = mapped_column(primary_key=True)
    roof_type: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    inspection_template_id: Mapped[int] = mapped_column(ForeignKey("inspection_templates.id"))

    inspection_template: Mapped["InspectionTemplate"] = relationship()


class InspectionTemplateItem(Base):
    """Einzelner Prüfpunkt einer Vorlage (seit 1.2.16). component_type (aus der Optionsgruppe
    roof_component_types) bestimmt, ob dieser Punkt beim Generieren genau einmal entsteht
    (component_type NULL) oder einmal je aktivem, nicht archiviertem RoofComponent passenden
    Typs der betroffenen Dachfläche. item_type ist ein festes Tupel im Code
    (INSPECTION_ITEM_TYPES in app/inspection_templates.py), keine Optionsgruppe -- die Werte
    steuern Renderlogik und Validierung, nicht nur eine Beschriftung."""

    __tablename__ = "inspection_template_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("inspection_templates.id"), index=True)
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    component_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    text: Mapped[str] = mapped_column(String(500))
    item_type: Mapped[str] = mapped_column(String(30))
    required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    target_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    target_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    photo_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    photo_before_after: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template: Mapped["InspectionTemplate"] = relationship(back_populates="items")


class InspectionItem(Base):
    """Konkreter Prüfpunkt eines Einsatzberichts (seit 1.2.16) -- entsteht durch Multiplikation
    einer InspectionTemplateItem gegen den Bauteilbestand einer Dachfläche
    (_generate_inspection_items() in app/service_reports.py). text/item_type/required/
    target_min/target_max/unit/die photo_*-Flags werden dabei PHYSISCH kopiert, nie zur
    Laufzeit von der Vorlage gelesen -- ändert sich die Vorlage später, ändert sich ein bereits
    erzeugter Bericht nicht rückwirkend. template_item_id/roof_component_id sind entsprechend
    reine, optionale Herkunftsangaben und dürfen ins Leere zeigen.

    roof_area_id (seit 1.2.22, Mehrflächen-Berichte) wird bei JEDER Generierung gesetzt --
    unabhängig davon, ob roof_component_id gesetzt ist. Für component-lose Punkte (component_type
    NULL auf der Vorlage) ist das der EINZIGE Weg, die Fläche zu kennen; für component-gebundene
    Punkte wäre roof_component.roof_area_id zwar redundant ableitbar, die direkte Spalte
    vermeidet aber einen Join bei jeder Gruppierung nach Fläche auf der Berichtsseite.

    client_uuid ist für den späteren Offline-Betrieb vorgesehen: ein mobiler Schreibvorgang
    bringt eine clientseitig erzeugte UUID mit, der Server nimmt sie idempotent an (die
    Warteschlange selbst kommt erst später, die Struktur aber schon jetzt). Der
    Unique-Constraint auf (service_report_id, client_uuid) funktioniert mit NULL wie gewünscht,
    da Standard-SQL NULL-Werte in einem UNIQUE-Constraint als paarweise verschieden behandelt
    -- beliebig viele Zeilen ohne client_uuid sind erlaubt, nur ein doppelter, tatsächlich
    gesetzter client_uuid auf demselben Bericht verstößt gegen den Constraint."""

    __tablename__ = "inspection_items"
    __table_args__ = (UniqueConstraint("service_report_id", "client_uuid", name="uq_inspection_item_client_uuid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_report_id: Mapped[int] = mapped_column(ForeignKey("service_reports.id"), index=True)
    template_item_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_template_items.id"), nullable=True)
    roof_component_id: Mapped[int | None] = mapped_column(ForeignKey("roof_components.id"), nullable=True)
    roof_area_id: Mapped[int | None] = mapped_column(ForeignKey("roof_areas.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column()
    group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text: Mapped[str] = mapped_column(String(500))
    item_type: Mapped[str] = mapped_column(String(30))
    required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    target_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    target_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    photo_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    photo_before_after: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ok|nok|na
    condition_grade: Mapped[int | None] = mapped_column(nullable=True)  # 1-4
    measured_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)  # nur leak_test
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    client_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template_item: Mapped["InspectionTemplateItem | None"] = relationship()
    roof_component: Mapped["RoofComponent | None"] = relationship()
    roof_area: Mapped["RoofArea | None"] = relationship()
    recorded_by_employee: Mapped["Employee | None"] = relationship()


class Finding(Base):
    """Mangel aus einem Einsatzbericht (seit 1.2.17) -- macht aus einem negativen Prüfergebnis
    eine Handlung. Die FESTSTELLUNG (description, severity, Bauteilbezug, Fotos) ist nach der
    Unterschrift des Berichts eingefroren; ihre NACHVERFOLGUNG (status, action von
    "zurueckgestellt" weg, resubmission_date, follow_up_*, closed_*) bleibt bewusst lebendig --
    ein Mangel wird oft erst Wochen nach der Unterschrift erledigt. Siehe
    update_finding_followup() in app/findings.py, die einzige Stelle, die nach der Unterschrift
    noch schreiben darf.

    status="zurueckgestellt" (unabhängig von action="zurueckgestellt", gleicher Wortlaut, zwei
    getrennte Konzepte): action ist die bei Anlage getroffene Entscheidung, status kann
    unabhängig davon jederzeit manuell so gesetzt werden."""

    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("service_report_id", "client_uuid", name="uq_finding_client_uuid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_report_id: Mapped[int] = mapped_column(ForeignKey("service_reports.id"), index=True)
    inspection_item_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_items.id"), nullable=True, index=True)
    roof_component_id: Mapped[int | None] = mapped_column(ForeignKey("roof_components.id"), nullable=True, index=True)
    # Physischer Namens-Schnappschuss (seit 1.3.12) -- roof_component_id selbst bleibt der FK
    # (Bauteilbezug ist laut Klassendocstring eingefroren, d.h. zeigt nie auf ein anderes Bauteil),
    # aber RoofComponent.name kann sich nach der Unterschrift ändern (Umbenennung); ohne diese
    # Spalte würde finding.roof_component.name den AKTUELLEN statt den damaligen Namen liefern.
    # Nullable, da Bestandszeilen ihn nicht rückwirkend historisch korrekt haben können (siehe
    # Migration, die ihn dort aus dem heutigen Namen befüllt statt leer zu lassen).
    roof_component_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(40))
    follow_up_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    follow_up_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    follow_up_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    resubmission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="offen", server_default="offen", index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    client_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    service_report: Mapped["ServiceReport"] = relationship(back_populates="findings")
    inspection_item: Mapped["InspectionItem | None"] = relationship()
    roof_component: Mapped["RoofComponent | None"] = relationship()
    closed_by_employee: Mapped["Employee | None"] = relationship(foreign_keys=[closed_by_employee_id])
    created_by_employee: Mapped["Employee | None"] = relationship(foreign_keys=[created_by_employee_id])
    # Nur Lesezugriff (kein cascade hier) -- die Löschkaskade läuft über
    # ServiceReport.photos (service_report_id), diese Relationship greift über die andere FK
    # (finding_id) auf dieselbe Tabelle zu, rein für den bequemen Zugriff finding.photos.
    photos: Mapped[list["ServiceReportPhoto"]] = relationship(back_populates="finding")


class ServiceReportPhoto(Base):
    """Foto zu einem Einsatzbericht (seit 1.2.17) -- gehört immer zu GENAU EINEM Prüfpunkt ODER
    GENAU EINEM Mangel, nie zu beidem, nie zu keinem (Business-Logik-Prüfung in
    app/service_reports.py::add_photo(), siehe dort für die Begründung gegen einen
    CheckConstraint). kind ("vorher"/"nachher"/"allgemein") ist nur bei einem Prüfpunkt mit
    photo_before_after relevant, sonst immer "allgemein"."""

    __tablename__ = "service_report_photos"
    __table_args__ = (UniqueConstraint("service_report_id", "client_uuid", name="uq_service_report_photo_client_uuid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_report_id: Mapped[int] = mapped_column(ForeignKey("service_reports.id"), index=True)
    inspection_item_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_items.id"), nullable=True, index=True)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20))
    file_path: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    client_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    inspection_item: Mapped["InspectionItem | None"] = relationship()
    finding: Mapped["Finding | None"] = relationship(back_populates="photos")
    created_by_employee: Mapped["Employee | None"] = relationship()


class ServiceReportMaterial(Base):
    """Verbrauchtes Material zu einem Einsatzbericht (seit 1.2.23) -- der Monteur erfasst nur,
    WAS verbraucht wurde, NIE einen Preis (bewusst keine Preisspalte hier); die Bepreisung
    passiert ausschließlich beim Rechnungslauf im Büro (create_invoice_from_time_entries() in
    app/invoices.py).

    Zwei gleichwertige Erfassungswege: material_id gesetzt (aus dem Katalog gewählt) kopiert
    description/unit als Schnappschuss aus Material -- ändert sich der Katalogeintrag später,
    bleibt hier stehen, was tatsächlich verbaut wurde. material_id leer (frei eingetippt) --
    description/quantity kommen direkt vom Monteur, es entsteht dabei NIE ein neuer
    Material-Katalogeintrag (der Katalog ist Stammdatenpflege des Büros).

    roof_area_id/inspection_item_id/finding_id sind alle unabhängig optional und schließen sich
    NICHT aus (anders als bei ServiceReportPhoto, das genau eins von beiden verlangt) --
    Material kann pauschal am Bericht hängen, einer Fläche zugeordnet sein und/oder zu einem
    konkreten Mangel gehören.

    Unveränderlich nach der Unterschrift (status="unterschrieben"), wie Prüfpunkte und Fotos --
    anders als beim Finding gibt es hier keinen lebendigen Nachverfolgungsteil, was verbaut
    wurde ändert sich nicht mehr. sign_report() bekommt dafür KEINE neue Pflichtprüfung, ein
    Einsatz ohne Materialverbrauch ist normal."""

    __tablename__ = "service_report_materials"
    __table_args__ = (
        UniqueConstraint("service_report_id", "client_uuid", name="uq_service_report_material_client_uuid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_report_id: Mapped[int] = mapped_column(ForeignKey("service_reports.id"), index=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    roof_area_id: Mapped[int | None] = mapped_column(ForeignKey("roof_areas.id"), nullable=True, index=True)
    inspection_item_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_items.id"), nullable=True, index=True)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    client_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    material: Mapped["Material | None"] = relationship()
    roof_area: Mapped["RoofArea | None"] = relationship()
    inspection_item: Mapped["InspectionItem | None"] = relationship()
    finding: Mapped["Finding | None"] = relationship()
    created_by_employee: Mapped["Employee | None"] = relationship()


class ServiceReportAsset(Base):
    """Eingesetztes Betriebsmittel an einem Einsatzbericht (seit 1.4.5, Betriebsmittelverwaltung
    Stufe 3) -- reine Dokumentation: KEINE Menge, KEINE Kosten, KEINE Betriebsstunden in dieser
    Version (siehe CLAUDE.md "Betriebsmittelverwaltung" -> Stufe 3).

    asset_id ist Pflicht (anders als ServiceReportMaterial.material_id) -- ein Betriebsmittel
    wird immer aus dem Katalog der freigegebenen Assets gewählt, nie frei eingetippt (siehe
    operational_assets.py::list_selectable_assets()). Trotzdem zusätzlich ein physischer
    Namens-Schnappschuss (asset_name_snapshot), dasselbe Muster wie
    Finding.roof_component_name_snapshot/ServiceReportRoofArea.roof_area_name_snapshot (seit
    1.3.12): ein unterschriebener Bericht ist ein Nachweis -- wird das Betriebsmittel (oder die
    zugrunde liegende, live aufgelöste OperationalResource) später umbenannt, darf sich die
    Anzeige eines bereits unterschriebenen Berichts nicht rückwirkend ändern. asset_id bleibt
    zusätzlich als echter Verweis erhalten (für eine spätere Kostenauswertung über den
    Katalogeintrag) -- delete_asset() (app/operational_assets.py) blockiert deshalb das Löschen
    eines Betriebsmittels, das noch in mindestens einem Einsatzbericht referenziert wird (Muster
    delete_roof_component()), damit asset_id nie ins Leere zeigt; Archivieren (active=False)
    bleibt dafür uneingeschränkt möglich.

    VORBEREITET FÜR SPÄTER, NICHT VORGEBAUT (dasselbe Muster wie client_uuid bei den Fotos,
    cost_notes am Betriebsmittel selbst): diese Tabelle ist die vorgesehene Stelle für die
    spätere Kosten-/Abrechnungserweiterung (Betriebsstunden, Mietdauer, abrechenbare Menge, die
    in eine Rechnung fließen) -- ein Datensatz je Einsatz, kein Name in einer Liste. Kommt diese
    Erweiterung, sind es nullable ALTER TABLE ADD COLUMN-Ergänzungen auf genau dieser Zeile,
    keine Strukturänderung. notes ist bewusst das einzige Zusatzfeld dieser Stufe und bleibt rein
    intern -- erscheint NIE im Kundenbericht (siehe app/service_report_pdf.py).

    Unveränderlich nach der Unterschrift (status="unterschrieben"), wie Material/Fotos/
    Prüfpunkte -- _require_draft_report() (app/service_reports.py) ist dieselbe Sperre."""

    __tablename__ = "service_report_assets"
    __table_args__ = (
        UniqueConstraint("service_report_id", "client_uuid", name="uq_service_report_asset_client_uuid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_report_id: Mapped[int] = mapped_column(ForeignKey("service_reports.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("operational_assets.id"), index=True)
    asset_name_snapshot: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    client_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    asset: Mapped["OperationalAsset"] = relationship()
    created_by_employee: Mapped["Employee | None"] = relationship()


class RoofLayerType(Base):
    """Schichttyp im Dachaufbau (seit 1.2.18) -- welche Schichten bei einer Dachfläche
    abgefragt werden, hängt vom Dachtyp ab (roof_type, NULL = gilt für jeden Dachtyp).
    option_group verweist auf den group_key einer SettingOptionGroup, aus der die Ausführung
    gewählt wird -- bewusst NICHT über den Leistungskatalog (Material/MaterialGroup): der
    Katalog dient der Preisfindung, der Dachaufbau der Dokumentation, was vor zwanzig Jahren
    verbaut wurde steht in keinem aktuellen Katalog. Ein Schichttyp ohne option_group
    (Konterlattung, Dachlattung, Trennlage, sowie die Gründach-spezifischen Schichten ohne
    definierte Ausführungsliste) hat in der Oberfläche nur den Ja/Nein-Umschalter und ein
    Bemerkungsfeld.

    Bekannte, bewusst offene Schwachstelle (siehe CLAUDE.md, "Bekannte, bewusst offene
    Punkte"): die Flachdach- und Gründach-Zeilen der Migrations-Seed-Daten sind aus
    Rücksicht auf roof_type als EINZELNES Feld je Schichttyp bewusst redundant (dieselbe
    Schicht unter zwei verschiedenen key-Werten) statt über eine Mehrfachzuordnung gelöst.

    has_execution/has_notes (seit 1.2.19): has_thickness war zu grob -- ein Schichttyp ohne
    option_group hat nie eine Ausführungsauswahl, unabhängig vom Flag; has_execution macht das
    explizit steuerbar (z. B. um eine vorhandene Ausführungsliste vorübergehend auszublenden,
    ohne option_group zu leeren). has_notes blendet das Bemerkungsfeld aus, wenn ein Schichttyp
    keine Freitext-Bemerkung braucht. Ein deaktiviertes Feld verschwindet nur aus der Anzeige --
    bereits erfasste Werte bleiben in der DB, die exclude_unset-Architektur von upsert_roof_layer()
    (siehe app/roof_areas.py) sendet ein nicht angezeigtes Feld nie mit, überschreibt es also
    nie."""

    __tablename__ = "roof_layer_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)
    label: Mapped[str] = mapped_column(String(120))
    roof_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    option_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    has_execution: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    has_thickness: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    has_notes: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    sort_order: Mapped[int] = mapped_column(default=100, server_default="100")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RoofLayer(Base):
    """Eine Schicht einer konkreten Dachfläche (seit 1.2.18) -- ersetzt RoofArea.build_up
    (Freitext) und RoofArea.insulation, die beide NICHT gelöscht wurden, aber seither nur noch
    historisch/schreibgeschützt sind (siehe dort). Ein RoofLayerType, der zum aktuellen
    RoofArea.roof_type nicht mehr passt (nach einem nachträglichen Dachtypwechsel), bleibt
    bewusst stehen -- Löschen wäre Datenverlust einer weiterhin wahren Aussage über das
    Gebäude, die Oberfläche kennzeichnet solche Zeilen nur als "passt nicht zum aktuellen
    Dachtyp" (app/roof_areas.py::list_roof_layers()).

    Seit 1.2.19 überschreibt upsert_roof_layer() nur noch tatsächlich mitgeschickte Felder
    (siehe dort) -- vorher überschrieb jeder Aufruf unbedingt alle vier Spalten, was in
    Kombination mit parallelen, ungebremsten Autosave-Aufrufen aus roof_area.html
    (setLayerPresent() + Bemerkungsfeld kurz danach) nachweislich zu Datenverlust führen
    konnte, wenn ein älterer Schnappschuss beim Server zuletzt committete."""

    __tablename__ = "roof_layers"
    __table_args__ = (UniqueConstraint("roof_area_id", "layer_type_id", name="uq_roof_layer_area_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    roof_area_id: Mapped[int] = mapped_column(ForeignKey("roof_areas.id"), index=True)
    layer_type_id: Mapped[int] = mapped_column(ForeignKey("roof_layer_types.id"), index=True)
    present: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    execution: Mapped[str | None] = mapped_column(String(160), nullable=True)
    thickness_mm: Mapped[int | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    layer_type: Mapped["RoofLayerType"] = relationship()


class OperationalAsset(Base):
    """Betriebsmittel (seit 1.4.0, Modul "betriebsmittel") -- die bewusste Form, wie
    OperationalResource für die Betriebsmittelverwaltung "erweitert" wird: NICHT durch
    zusätzliche Spalten auf OperationalResource selbst, sondern durch eine eigene
    Inventarschicht mit optionalem Bezug zu genau einer Ressource. Ein Kran ist ein
    Betriebsmittel MIT Ressourcenbezug (inventarisiert und in der Plantafel disponierbar
    über den unverändert bestehenden Weg Team/TeamResource), eine Leiter ein
    Betriebsmittel OHNE (nie in der Disposition, aber trotzdem inventarisiert/prüfpflichtig).

    Verhindert Doppelerfassung: resource_id ist unique (höchstens ein Asset je Ressource)
    UND die eigenen Identitätsfelder (name/asset_type/manufacturer/model/identifier) bleiben
    NULL, solange resource_id gesetzt ist -- Anzeige/API lösen sie in diesem Fall IMMER live
    von der verknüpften OperationalResource auf (operational_assets.py::asset_to_dict()),
    nie als eigene Kopie. Ist resource_id NULL, sind die eigenen Felder die einzige Quelle,
    name ist dann Pflicht (in der Business-Logik geprüft, nicht per DB-Constraint, da das
    Feld für den verknüpften Fall NULL bleiben muss).

    WARNUNG für künftige Änderungen: OperationalResource und OperationalAsset NICHT zu einer
    einzigen Tabelle zusammenführen -- die Plantafel/Team-Disposition (Team, TeamResource,
    WorkPreparationTeamResource, PlanningSlot) referenziert ausschließlich
    operational_resources.id und kennt OperationalAsset überhaupt nicht. Eine Zusammenführung
    würde diese Fremdschlüssel brechen oder eine Migration alter IDs erfordern -- genau das
    Risiko, vor dem diese getrennte Tabelle bewusst schützt.

    recurring_cost_per_month (Spalte entfernt, seit "Betriebsmittel-Kosten fest als
    Kostenposten"): die frühere, monatsnormalisierte Schnellnotiz ist einer echten Verknüpfung
    zu RecurringCost gewichen -- ein hier eingetragener Betrag erzeugt/ändert/entfernt seither
    einen vollwertigen RecurringCost mit RecurringCost.is_asset_quick_entry=True (siehe dort),
    statt nur eine Zahl auf dieser Zeile zu speichern. asset_to_dict() (app/operational_assets.py)
    liefert recurring_cost_per_month als API-Feld unverändert weiter, jetzt aber LIVE aus dem
    verknüpften Kostenposten gelesen, nicht mehr aus einer eigenen Spalte.

    selectable_in_reports (seit 1.4.5, Betriebsmittelverwaltung Stufe 3): steuert, ob dieses
    Betriebsmittel in der Auswahlliste eines Einsatzberichts erscheint (list_selectable_assets()
    in app/operational_assets.py) -- Standard AUS (server_default='0'), dasselbe restriktive
    Vorgabemuster wie DocumentCategory.is_field_visible: das Büro gibt bewusst frei, was in einen
    Bericht darf, statt dass jedes Kleingerät die Liste zuwachsen lässt. Nur über die
    Betriebsmittel-Bearbeitungsseite (Büro/Admin) änderbar."""

    __tablename__ = "operational_assets"
    __table_args__ = (UniqueConstraint("resource_id", name="uq_operational_asset_resource"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("operational_resources.id"), nullable=True, index=True)
    asset_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Nur befüllt/gültig, wenn resource_id NULL ist (eigenständiges Betriebsmittel).
    name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    asset_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    identifier: Mapped[str | None] = mapped_column(String(120), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Beschaffung (seit Stufe 2) -- Büro/Admin-only, siehe OperationalAssetFieldOut: ein Monteur
    # sieht diese beiden Felder an keiner Stelle, sie gehören zur Beschaffung, nicht zur Bedienung.
    article_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Bedienungshinweise (seit Stufe 2) -- bewusst ein EIGENES Feld, getrennt von notes: notes
    # kann beliebige interne/Beschaffungs-Vermerke enthalten, usage_notes ist das einzige
    # Freitextfeld, das ein Monteur über die rollenabhängige Betriebsmittelseite zu sehen bekommt.
    usage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    acquisition_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    acquisition_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    selectable_in_reports: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resource: Mapped["OperationalResource | None"] = relationship()
    inspections: Mapped[list["OperationalAssetInspection"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan", order_by="OperationalAssetInspection.next_due_date"
    )
    documents: Mapped[list["OperationalAssetDocument"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan", order_by="OperationalAssetDocument.uploaded_at.desc()"
    )


class OperationalAssetInspection(Base):
    """Prüf-/Wartungsfrist eines Betriebsmittels (seit 1.4.0) -- eigenes, frisches
    Fälligkeitsmuster (is_inspection_due()/is_inspection_overdue() in
    app/operational_assets.py), bewusst NICHT dieselben Funktionen wie
    MaintenanceContractItem (app/maintenance_contracts.py) wiederverwendet: deren
    _is_item_overdue() ist an die saisonalen MaintenanceWindow-Fenster der Wartungsverträge
    gekoppelt, was für eine turnusmäßige Gerätefrist (z. B. jährliche UVV-Prüfung) fachlich
    nicht passt. Das PATTERN (Vorlaufzeit-gesteuertes is_due, eigenständiges is_overdue) ist
    identisch übernommen -- exakt die "gleiches Muster, dokumentierte Trennung"-Vorgabe wie
    bei den Pipeline-Spalten (siehe CLAUDE.md).

    next_due_date wird seit 1.4.2 automatisch berechnet (app/operational_assets.py::
    _compute_next_due_date()), sobald interval_months gesetzt ist -- IMMER vom tatsächlichen
    last_inspection_date aus (oder, ohne dieses, vom Anschaffungsdatum des Betriebsmittels),
    NIE kumulativ fortgeschrieben. Eine Prüffrist ohne interval_months (einmalige Prüfung)
    bleibt vollständig manuell, next_due_date kommt dann direkt vom Client.
    last_reminder_due_date ist derselbe Idempotenz-Stempel wie MaintenanceContract.
    last_reminder_due_date (siehe dort) -- verhindert eine doppelte Erinnerungs-Aufgabe für
    denselben Fälligkeitstermin, bewusst NIE explizit zurückgesetzt: ändert sich next_due_date
    (Neuberechnung nach einer Prüfung), unterscheidet es sich automatisch vom alten Stempel,
    ein Reset wäre redundant."""

    __tablename__ = "operational_asset_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("operational_assets.id"), index=True)
    inspection_type: Mapped[str] = mapped_column(String(80), index=True)
    interval_months: Mapped[int | None] = mapped_column(nullable=True)
    last_inspection_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    inspector: Mapped[str | None] = mapped_column(String(160), nullable=True)
    document_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_reminder_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    asset: Mapped[OperationalAsset] = relationship(back_populates="inspections")


class OperationalAssetDocument(Base):
    """Dokumentenablage je Betriebsmittel (seit 1.4.2, Punkt 4) -- Anschaffungsrechnung,
    Leasingvertrag u. Ä. Bewusst eine SCHLANKE, eigene Ablage OHNE die volle DocumentCategory-
    Stammdatentabelle aus 1.3.62 (Kunden-/Projektdokumente): DocumentCategory trägt
    is_sensitive/is_field_visible -- zwei Schlösser gegen "sensible Kategorie für Monteure
    sichtbar". Diese Achse existiert hier gar nicht: ALLE Betriebsmittel-Dokumente sind
    ausnahmslos Büro/Admin-only, auch über den QR-Code nie erreichbar (OperationalAssetFieldOut
    kennt dieses Feld an keiner Stelle, siehe app/schemas.py) -- ein Kategorie-Schloss für eine
    Stufe, die es nie gibt, wäre nur Ballast. document_type ist deshalb ein einfaches, freies
    String-Feld, per Dropdown aus der self-seedenden Optionsgruppe
    operational_asset_document_types befüllt -- exakt dasselbe, bereits etablierte Muster wie
    OperationalAssetInspection.inspection_type, nicht die schwergewichtigere Stammdatentabelle.

    Löschen: eine echte cascade="all, delete-orphan"-Relationship auf OperationalAsset.documents
    UND ein before_delete-Event (app/operational_assets.py, Muster app/roof_areas.py::
    _delete_roof_area_sketch_file()) räumen die Datei von der Festplatte auf -- feuert für
    JEDEN ORM-Löschweg, auch kaskadiert beim Löschen des ganzen Betriebsmittels."""

    __tablename__ = "operational_asset_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("operational_assets.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(80), index=True)
    stored_filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset: Mapped[OperationalAsset] = relationship(back_populates="documents")


class OperationalAssetSettings(Base):
    """Einstellungen für das Modul "betriebsmittel" (seit 1.4.0), Singleton wie
    MaintenanceSettings/TaskSettings (immer genau eine Zeile mit id=1).
    reminder_lead_days steuert, ab wie vielen Tagen VOR next_due_date eine Prüffrist bereits
    als fällig gilt -- dasselbe Konzept wie MaintenanceSettings.reminder_lead_days, aber eine
    eigene, unabhängige Einstellung (kein gemeinsamer Datensatz mit dem Wartungsmodul)."""

    __tablename__ = "operational_asset_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    reminder_lead_days: Mapped[int] = mapped_column(default=30, server_default="30")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecurringCost(Base):
    """Kostenposten der Betriebskosten-Übersicht (seit 1.5.0, Modul "betriebskosten") --
    Schicht 1: reine Erfassung wiederkehrender Verträge (Miete, Leasing, Versicherung,
    Software-Abo u. Ä.). Bewusst KEINE Migration der bestehenden
    OperationalAsset.acquisition_cost/recurring_cost_per_month -- die monthly_cost am
    Betriebsmittel ist eine schnelle Notiz beim Anlegen, dieser Kostenposten der detaillierte
    Vertrag mit Partner/Kündigungsfrist/Dokument. Beide Quellen bestehen nebeneinander,
    recurring_costs.py::overview_summary() führt sie in der Summe zusammen.

    annual_amount ist ein GESPEICHERTES, normiertes Feld -- berechnet von
    normalize_to_annual() (recurring_costs.py) bei jedem Anlegen/Ändern, NICHT bei jeder
    Summierung neu aus amount/billing_interval berechnet. **ANDOCKPUNKT für den späteren
    Verrechnungssatz-Kreislauf**: Schicht 3 summiert annual_amount über alle aktiven Posten
    und speist das Ergebnis in LaborRateOverheadSettings.fixed_overhead_value (Modus "eur")
    ein -- siehe app/labor_rate.py::calculate_labor_rate(), dort ist `fixed_overhead` bereits
    heute die Summe genau solcher Fixkosten, nur noch händisch einzutragen. Diese Spalte ist
    der Wert, den ein künftiger automatischer Kreislauf dort einsetzen wird -- keine neue
    Stelle nötig, nur diese eine Summe.

    net_amount/tax_rate_pct/gross_amount (seit "Netto und Brutto bei den Betriebskosten"): das
    ursprüngliche, einzelne Feld hieß "amount" und wurde OHNE jede Steuersemantik geführt --
    weder das Modell noch normalize_to_annual() kannten einen Steuersatz. Da 0 Bestandszeilen
    existierten (real geprüft), war die Umbenennung auf net_amount folgenlos für Bestandsdaten,
    aber inhaltlich die einzig konsistente Lesart: annual_amount speiste (und speist weiterhin)
    direkt in den Verrechnungssatz-Kreislauf, und ein Aufwand für die Kalkulation ist immer der
    Netto-Betrag, nie inklusive der abzugsfähigen Vorsteuer. gross_amount wird NIE gespeichert,
    NIE in annual_amount verrechnet -- reine Anzeige-Ableitung wie cancellation_deadline() unten.

    asset_id ist OPTIONAL: ein Betriebsmittel kann mehrere unabhängige Kostenposten tragen
    (z. B. Leasingrate UND Versicherung für denselben Transporter) -- deshalb absichtlich KEIN
    Unique-Constraint auf asset_id selbst.

    is_asset_quick_entry (seit "Betriebsmittel-Kosten fest als Kostenposten") markiert den
    EINEN Kostenposten je Betriebsmittel, der von dessen eigenem "Laufende Kosten je Monat"-Feld
    (operational_asset.html) automatisch erzeugt/geändert/entfernt wird -- siehe
    app/operational_assets.py::sync_asset_recurring_cost(). Jeder andere, über die allgemeine
    Betriebskosten-Oberfläche verknüpfte Posten für dasselbe asset_id bleibt is_asset_quick_entry=
    False und damit vom Betriebsmittel-Formular unberührt (die Leasingrate-UND-Versicherung-
    Kombination bleibt dadurch möglich). "Höchstens ein is_asset_quick_entry=True-Posten je
    asset_id" ist eine reine ANWENDUNGS-Invariante (sync_asset_recurring_cost() sucht immer
    zuerst den bestehenden, bevor ein neuer angelegt wird) -- bewusst KEIN DB-Constraint dafür,
    dieselbe Zurückhaltung wie beim fehlenden Unique-Constraint auf asset_id selbst oben. Die
    frühere Doppelzählungs-Sonderbehandlung aus 1.5.0 (OperationalAsset.recurring_cost_per_month
    als zweite, parallele Kostenquelle neben RecurringCost) ist mit dieser Version ersatzlos
    entfallen -- RecurringCost ist seither die EINZIGE Quelle für Betriebsmittel-Kosten.

    billing_interval ist ein fester Code-Wert (BILLING_INTERVALS in recurring_costs.py, keine
    Optionsgruppe -- wie SEVERITIES/ACTIONS/STATUSES bei Finding). "einmalig" ist bereits ein
    gültiger Wert (kein DB-Constraint auf dieser Spalte, nur Pydantic prüft die erlaubte
    Menge) -- normalize_to_annual() liefert dafür bewusst 0 (kein laufender Jahresbetrag,
    fließt nicht in die wiederkehrende Summe ein), der Posten selbst bleibt sichtbar. Eine
    eigene Erfassungsoberfläche für einmalige Kosten ist NICHT Teil von Schicht 1 -- das
    Modell steht ihr nicht im Weg, siehe CLAUDE.md."""

    __tablename__ = "recurring_costs"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    # net_amount ist die Eingabe (seit "Netto und Brutto bei den Betriebskosten") -- annual_amount
    # (unten) wird ausschließlich daraus berechnet, NIE aus einem Bruttobetrag: die Vorsteuer ist
    # ein durchlaufender Posten, kein Aufwand, der in den Verrechnungssatz-Kreislauf einfließen
    # darf. tax_rate_pct ist bewusst ein Feld JE POSTEN, kein globaler Wert -- ein
    # Steuerberater-Honorar mit 19 % und eine Versicherung mit 0 % stehen nebeneinander (siehe
    # TAX_RATES in recurring_costs.py). gross_amount ist eine reine, nicht gespeicherte Anzeige-
    # Ableitung aus net_amount/tax_rate_pct (Muster cancellation_deadline() unten -- was
    # tatsächlich vom Konto abgeht, aber nie Rechenbasis für annual_amount).
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax_rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("19.00"), server_default="19.00")
    billing_interval: Mapped[str] = mapped_column(String(20))
    annual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Kalkulatorische Einordnung für den Verrechnungssatz-Kreislauf (Schicht 3, seit 1.5.1) --
    # fester Code-Wert (OVERHEAD_CLASSIFICATIONS in recurring_costs.py, keine Optionsgruppe --
    # dieselbe Rechenregel-vs-freie-Auswahl-Unterscheidung wie bei billing_interval). "keine"
    # ist der restriktive Default: ein Posten fließt erst nach bewusster Einordnung in eine der
    # beiden Gemeinkosten-Summen ein. Werte vermeiden bewusst das Wort "variabel" (siehe
    # CLAUDE.md "Betriebskosten-Übersicht" -> "Terminologie 'variabel'") -- "fix"/
    # "auslastungsabhaengig"/"keine".
    overhead_classification: Mapped[str] = mapped_column(
        String(20), default="keine", server_default="keine", index=True
    )
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notice_period_months: Mapped[int | None] = mapped_column(nullable=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("operational_assets.id"), nullable=True, index=True)
    is_asset_quick_entry: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_reminder_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    asset: Mapped["OperationalAsset | None"] = relationship()
    documents: Mapped[list["RecurringCostDocument"]] = relationship(
        back_populates="cost", cascade="all, delete-orphan", order_by="RecurringCostDocument.uploaded_at.desc()"
    )


class RecurringCostDocument(Base):
    """Dokumentenablage je Kostenposten (seit 1.5.0) -- Vertrag, Rechnung, Kündigungsschreiben
    u. Ä. Muster OperationalAssetDocument (1.4.2): mehrere unabhängige Dateien je Kostenposten,
    document_type aus der self-seedenden Optionsgruppe recurring_cost_document_types statt
    einer schwergewichtigen Stammdatentabelle -- Kostenposten-Dokumente sind ausnahmslos
    Büro/Admin-only, keine Feld-sichtbare Stufe existiert. Löschen räumt die Datei über ein
    before_delete-Event auf (app/recurring_costs.py, Muster app/roof_areas.py)."""

    __tablename__ = "recurring_cost_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    recurring_cost_id: Mapped[int] = mapped_column(ForeignKey("recurring_costs.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(80), index=True)
    stored_filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cost: Mapped[RecurringCost] = relationship(back_populates="documents")


class RecurringCostSettings(Base):
    """Einstellungen für das Modul "betriebskosten" (seit 1.5.0), Singleton wie
    OperationalAssetSettings/TaskSettings (immer genau eine Zeile mit id=1).
    reminder_lead_days steuert, ab wie vielen Tagen VOR der berechneten Kündigungsfrist eine
    Aufgabe erzeugt wird -- eigene, unabhängige Einstellung, kein gemeinsamer Datensatz mit
    einem anderen Modul."""

    __tablename__ = "recurring_cost_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    reminder_lead_days: Mapped[int] = mapped_column(default=30, server_default="30")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Account(Base):
    """Sachkonto (Kontenstamm, Buchhaltung Stufe 2 -- erster Teil, Modul "buchhaltung") --
    für die Vorkontierung von Eingangsrechnungen, Nummernkreis nach SKR 04. Reine
    Verwaltungstabelle wie `TaxKey`/`PaymentTerm` (Kontonummer + Bezeichnung + optionaler
    Standard-Steuersatz -- mehr als ein Label, deshalb echte Tabelle statt Optionsgruppe).

    **Bewusst KEIN Startbestand mit vorbelegten SKR-04-Nummern** -- siehe CLAUDE.md
    "Buchhaltung" -> "Kontenstamm" für die volle Begründung: bei den tatsächlich benötigten
    Aufwandskonten (Wareneinkauf/Miete/Versicherung/Fremdleistungen usw.) ließ sich die vom
    Auftrag geforderte Zahlengenauigkeit ("echte SKR-04-Nummern, keine erfundenen") ohne eine
    verifizierbare Quelle nicht mit der nötigen Sicherheit garantieren -- die Tabelle bleibt
    leer, bis der Betreiber Konten manuell anlegt (z. B. nach Rücksprache mit dem
    Steuerberater) oder der spätere Datei-Import (Stufe 2, zweiter Teil, noch nicht gebaut)
    sie befüllt.

    default_tax_rate_pct ist NUR EIN VORSCHLAG (viele Konten haben einen typischen Satz -- ein
    Wareneinkaufskonto 19 %, ein Versicherungskonto 0 %): beim Wählen eines Kontos an einer
    Eingangsrechnung/-position wird er client-seitig vorbelegt, ist aber jederzeit
    übersteuerbar -- DIE RECHNUNG entscheidet den tatsächlichen Steuersatz, nicht das Konto.
    Kein serverseitiger Zwang, keine Ableitung aus dem Konto beim Speichern.

    active statt Löschen -- kein Löschen vorgesehen (auch für ein nie verwendetes Konto), nur
    Archivieren/Aktivieren (Muster `TaxKey.archived`, hier als einzelnes Bool statt eines
    zusätzlichen "ist Standard"-Zustands, den es hier nicht gibt).

    **ANDOCKPUNKT für den späteren Import der Steuerberater-Kontendatei** (Stufe 2, zweiter
    Teil, NICHT Teil dieser Version): ein künftiger Import liest die Kontendatei und legt für
    jede Zeile über `account_number` (Unique-Constraint, der stabile natürliche Schlüssel) ein
    Konto an oder aktualisiert es (Upsert) -- `app/accounts.py::create_account()`/
    `update_account()` validieren bereits alles Nötige, keine Änderung an der Tabelle oder an
    diesen Funktionen nötig, wenn der Import gebaut wird.

    **Vorkontierung, keine Buchung**: siehe `IncomingInvoice.account_id` unten -- das ERP nimmt
    an keiner Stelle eine steuerliche Bewertung vor, der Steuerberater prüft und bucht."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("account_number", name="uq_account_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_number: Mapped[str] = mapped_column(String(20), index=True)
    label: Mapped[str] = mapped_column(String(255))
    default_tax_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IncomingInvoice(Base):
    """Eingangsrechnung (Buchhaltung Stufe 1, Modul "buchhaltung") -- vorbereitende Erfassung
    und Ablage empfangener Lieferantenrechnungen. Bewusst eine EIGENE Tabelle, getrennt von
    Invoice (Ausgangsrechnung): Ein- und Ausgang sind fachlich verschiedene Domänen -- eine
    Eingangsrechnung ist ein empfangenes externes Dokument mit von Anfang an fixen Werten
    (so wie der Lieferant sie geschrieben hat), keine selbst erzeugte, versendete
    GoBD-Unveränderlichkeits-/Snapshot-Mechanik wie bei Invoice.

    net_amount/tax_rate_pct sind der GESAMTBETRAG der Rechnung -- immer vorhanden, unabhängig
    davon, ob Positionen (IncomingInvoiceItem) existieren. gross_amount wird NIE gespeichert
    (Muster RecurringCost.gross_amount()) -- reine Anzeige-Ableitung, aus den Positionen
    summiert, wenn vorhanden, sonst aus net_amount*(1+tax_rate_pct/100), siehe
    app/incoming_invoices.py::invoice_gross_amount().

    Positionen sind OPTIONAL (Betreiberentscheidung, siehe CLAUDE.md "Buchhaltung"): eine
    einfache Rechnung bleibt ein Gesamtbetrag, eine mit gemischten Steuersätzen wird
    aufgeschlüsselt. net_amount bleibt auch bei vorhandenen Positionen die maßgebliche Summe --
    create_invoice()/update_invoice() (app/incoming_invoices.py) prüfen, dass die Netto-Summe
    der Positionen zum Gesamtbetrag passt, und melden eine Abweichung (ValueError), statt sie
    still zuzulassen.

    payment_status trägt NUR "offen"/"bezahlt" -- "überfällig" wird NICHT gespeichert, sondern
    bei jedem Lesezugriff berechnet (app/incoming_invoices.py::is_overdue()), exakt konsistent
    mit Invoice (app/invoices.py: is_overdue = status=="versendet" and due_date < date.today()).
    Ein gespeicherter dritter Statuswert würde veralten, sobald das Datum verstreicht, ohne dass
    irgendetwas ihn nachzieht.

    Zuordnung: project_id/asset_id/recurring_cost_id sind alle optional, höchstens EINE davon
    darf gesetzt sein -- geprüft in der Business-Logik (Muster ServiceReportPhoto: "gehört immer
    zu GENAU EINEM ... ODER ..., nie zu beidem/keinem", bewusst kein CheckConstraint). Eine
    Rechnung kann auch unzugeordnet bleiben.

    **ANDOCKPUNKT Verrechnungssatz-Kreislauf (bestätigte, dauerhafte architektonische Grenze,
    siehe CLAUDE.md "Buchhaltung")**: recurring_cost_id verbindet eine Eingangsrechnung mit dem
    geplanten Kostenposten, gegen den sie gebucht wird -- das ist AUSSCHLIESSLICH für Anzeige/
    Plan-Ist-Vergleich gedacht. KEINE Funktion dieses Projekts darf darüber RecurringCost.
    annual_amount/den Verrechnungssatz (Schicht 3) verändern -- der geplante Kostenposten
    bleibt die alleinige Grundlage, die Eingangsrechnung ist ausschließlich der Beleg dagegen.

    document_filename/document_original_name: EIN Beleg je Rechnung, 1:1-Muster wie
    OperationalAssetInspection.document_filename (ersetzt die vorherige Datei beim erneuten
    Hochladen, app/incoming_invoice_documents.py) -- keine Mehrfachablage wie bei
    OperationalAssetDocument/RecurringCostDocument, da eine Eingangsrechnung fachlich genau
    einen Beleg hat.

    **Vorkontierung seit Buchhaltung Stufe 2 (erster Teil)**: account_id (hier UND auf
    IncomingInvoiceItem) verweist optional auf ein Sachkonto (`Account`, Kontenstamm) --
    GENAU EINES von beiden trägt das Konto, je nachdem ob die Rechnung aufgeschlüsselt ist
    (siehe app/incoming_invoices.py::is_invoice_accounted()). War in Stufe 1 ein freies
    Freitextfeld `account_code` (String) -- da zum Zeitpunkt der Umstellung 0 reale Zeilen
    existierten, wurde die Spalte ersetzt (DROP + neue FK-Spalte), keine Backfill-Migration
    nötig, siehe CLAUDE.md "Buchhaltung" -> "Kontenstamm" für die Begründung, warum eine echte
    FK sauberer ist als ein Verweis per Kontonummer-String. **Das ist eine VORKONTIERUNG, kein
    finaler Buchungssatz** -- der Steuerberater prüft und bucht, das ERP nimmt an keiner Stelle
    eine steuerliche Bewertung vor. `Account.default_tax_rate_pct` liefert beim Wählen nur einen
    Vorschlag für `tax_rate_pct` -- die Rechnung/Position entscheidet den tatsächlichen Satz,
    nicht das Konto.

    **ANDOCKPUNKT Stufe 2, zweiter Teil (DATEV-Export, NICHT Teil dieser Version)**: sobald
    Vorkontierungen vorliegen, liest ein künftiger Export `account_id`/`Account.account_number`
    -- keine weitere Vorbereitung an diesem Modell nötig.

    **ANDOCKPUNKT Stufe 3 (KI-Belegauswertung)**: supplier_id/supplier_invoice_number/
    invoice_date/net_amount/tax_rate_pct/due_date/skonto_percent/skonto_deadline sind exakt die
    Felder, die eine künftige automatische Belegauswertung füllen würde -- 1:1, keine
    Umstrukturierung nötig, wenn Stufe 3 kommt."""

    __tablename__ = "incoming_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    supplier_invoice_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax_rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("19.00"), server_default="19.00")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    skonto_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    skonto_deadline: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    payment_status: Mapped[str] = mapped_column(String(20), default="offen", server_default="offen", index=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("operational_assets.id"), nullable=True, index=True)
    recurring_cost_id: Mapped[int | None] = mapped_column(ForeignKey("recurring_costs.id"), nullable=True, index=True)
    # Vorkontierung (Stufe 2) -- siehe Klassendocstring oben. Nur relevant, wenn KEINE
    # Positionen existieren (sonst trägt jede IncomingInvoiceItem ihr eigenes Konto).
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Idempotenz-Stempel für check_due_skonto_and_create_reminders() (Muster
    # RecurringCost.last_reminder_due_date) -- OHNE expliziten Reset, siehe dort.
    last_skonto_reminder_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    supplier: Mapped["Supplier"] = relationship()
    project: Mapped["Project | None"] = relationship()
    asset: Mapped["OperationalAsset | None"] = relationship()
    recurring_cost: Mapped["RecurringCost | None"] = relationship()
    account: Mapped["Account | None"] = relationship()
    items: Mapped[list["IncomingInvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="IncomingInvoiceItem.id"
    )


class IncomingInvoiceItem(Base):
    """Optionale Positions-Aufschlüsselung einer Eingangsrechnung (Buchhaltung Stufe 1) -- nur
    nötig, wenn die Rechnung mehrere Steuersätze mischt (z. B. Material 19 % + eine steuerfreie
    Position). IncomingInvoice.net_amount bleibt auch bei vorhandenen Positionen die
    maßgebliche Gesamtsumme -- die Positionen sind eine Aufschlüsselung, keine Ersetzung, ihre
    Netto-Summe muss dazu passen (siehe app/incoming_invoices.py). Beim Speichern der Rechnung
    werden alle Positionen vollständig ersetzt (kein Teil-Update einzelner Zeilen) -- Stufe 1
    kennt keine Positions-eigene Historie, das ist für die manuelle Erfassung ausreichend.

    account_id: dieselbe Vorkontierung wie am Header (Buchhaltung Stufe 2), hier je Position --
    eine gemischte Rechnung trägt ihr Konto pro Position statt am Header (siehe
    IncomingInvoice.account_id-Dokumentation oben)."""

    __tablename__ = "incoming_invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    incoming_invoice_id: Mapped[int] = mapped_column(ForeignKey("incoming_invoices.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax_rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("19.00"), server_default="19.00")
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)

    invoice: Mapped[IncomingInvoice] = relationship(back_populates="items")
    account: Mapped["Account | None"] = relationship()


class IncomingInvoiceSettings(Base):
    """Einstellungen für das Modul "buchhaltung" (Buchhaltung Stufe 1), Singleton wie
    RecurringCostSettings/OperationalAssetSettings (immer genau eine Zeile mit id=1).
    skonto_reminder_lead_days steuert, ab wie vielen Tagen VOR der Skontofrist eine Warnung
    erscheint -- eigene, unabhängige Einstellung, kein gemeinsamer Datensatz mit einem anderen
    Modul."""

    __tablename__ = "incoming_invoice_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    skonto_reminder_lead_days: Mapped[int] = mapped_column(default=5, server_default="5")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AISettings(Base):
    """Fundament für künftige KI-Funktionen (Belegauswertung, Angebotstexte,
    Berichtszusammenfassung) -- reine Konfiguration für die zentrale Schnittstelle
    app/ai_service.py::call_ai(). In DIESER Runde nutzt KEINE Fachfunktion das, nur das
    Fundament selbst (siehe CLAUDE.md "KI-Fundament" für die volle Herleitung).

    Singleton wie SmtpSettings (immer genau eine Zeile mit id=1). Nur für Administratoren --
    Systemkonfiguration, nicht einmal buero_finanzen (Betreibervorgabe, app/routers/
    ai_settings.py).

    enabled ist der Gesamtschalter, Default AUS -- solange kein AV-Vertrag mit einem Anbieter
    steht, bleibt jede KI-Funktion ausgeschaltet, unabhängig davon, ob bereits ein Anbieter/
    Schlüssel eingetragen ist (call_ai() prüft ihn zuerst, vor jeder Netzwerkaktivität).

    provider ist NULL im Normalzustand ("kein Anbieter konfiguriert") oder einer der vier Werte
    aus AI_PROVIDERS (app/ai_types.py) -- fester Code-Wert wie RecurringCost.billing_interval,
    keine Optionsgruppe, da die Auswahl bestimmt, welcher Adapter dispatcht wird. In dieser
    Runde ist für KEINEN der vier ein echter Adapter hinterlegt (siehe app/ai_adapters.py) --
    call_ai() liefert dann AIProviderNotConfigured, unabhängig vom gewählten Wert.

    api_key_encrypted: wie SmtpSettings.password_encrypted, über app/crypto.py
    (encrypt_secret/decrypt_secret), nie im Klartext zurückgegeben (siehe
    AISettingsOut.has_api_key). api_base_url/model sind reiner Freitext, sichtbar in den
    Einstellungen -- damit erkennbar ist, wohin Daten gehen würden (Datenschutz-Rahmen)."""

    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    api_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AICallLog(Base):
    """Protokoll jedes KI-Aufrufs (Zeitpunkt, aufrufende Funktion, Erfolg/Fehler, Token/Kosten
    wenn geliefert) -- siehe app/ai_service.py::call_ai(), die einzige Stelle, die hier
    schreibt. NIEMALS der Anfrage- oder Antwortinhalt selbst (kein Prompt, kein Beleg/Bild,
    keine Antwort) -- das ist eine ausdrückliche Zusage, keine Bequemlichkeit: die KI-Anfrage
    geht an den Adapter und ist danach vollständig weg, sie wird an KEINER Stelle im ERP
    gespeichert, auch nicht zwischenzeitlich in einem Cache oder Debug-Log. error_type ist der
    reine Exception-Klassenname, nie dessen Text (der könnte bei einem echten Anbieter-Adapter
    Teile der Anfrage/Antwort enthalten).

    ANDERS als FailedLoginAttempt (siehe dort) bewusst OHNE automatische Bereinigung -- der
    Zweck ist hier nicht kurzlebige Sicherheits-Buchhaltung, sondern dass der Betreiber über
    die Zeit sieht, was die KI kostet und ob sie funktioniert (Betreibervorgabe). Die Tabelle
    bleibt wie AuditLog dauerhaft bestehen, kein Aufräumjob."""

    __tablename__ = "ai_call_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    caller: Mapped[str] = mapped_column(String(80), index=True)
    success: Mapped[bool] = mapped_column(Boolean)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
