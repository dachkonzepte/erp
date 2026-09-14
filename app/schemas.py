from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    article_number: str | None
    quantity: Decimal
    unit: str
    waste_raw: Decimal
    purchase_price: Decimal
    price_basis: Decimal


class ServiceListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    source_type: str
    short_text: str
    unit: str
    site_time_raw: Decimal
    sale_price: Decimal
    activity_code: str | None
    material_count: int
    catalog_id: int | None = None
    catalog_name: str | None = None
    calculated_sale_price: Decimal | None = None
    calculation_delta: Decimal | None = None


class ServiceDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    catalog_id: int | None
    service_type: str | None
    external_id: str
    title_name: str | None
    short_text: str
    long_text: str
    quantity: Decimal
    unit: str
    site_time_raw: Decimal
    workshop_time_raw: Decimal
    time_unit: str | None
    sale_price: Decimal
    activity_code: str | None
    materials: list[MaterialOut]


class ImportSummary(BaseModel):
    filename: str
    source_name: str
    source_version: str | None
    title_count: int
    position_count: int
    material_item_count: int
    inserted_services: int
    replaced_services: int


class CalculationSettingsOut(BaseModel):
    labor_rate: Decimal
    material_markup_pct: Decimal
    overhead_pct: Decimal
    risk_profit_pct: Decimal
    use_source_time_as_minutes: bool


class CalculationSettingsUpdate(BaseModel):
    labor_rate: Decimal = Field(ge=0)
    material_markup_pct: Decimal = Field(ge=-100)
    overhead_pct: Decimal = Field(ge=-100)
    risk_profit_pct: Decimal = Field(ge=-100)
    use_source_time_as_minutes: bool = True


class MaterialOverrideIn(BaseModel):
    material_id: int
    quantity_override: Decimal | None = None
    waste_pct: Decimal = Field(default=Decimal("0"), ge=-100)
    purchase_price_override: Decimal | None = Field(default=None, ge=0)
    price_basis_override: Decimal | None = Field(default=None, gt=0)


class ServiceCalculationUpdate(BaseModel):
    site_time_minutes: Decimal | None = Field(default=None, ge=0)
    workshop_time_minutes: Decimal | None = Field(default=None, ge=0)
    labor_rate_override: Decimal | None = Field(default=None, ge=0)
    material_markup_pct_override: Decimal | None = Field(default=None, ge=-100)
    equipment_cost: Decimal = Field(default=Decimal("0"), ge=0)
    subcontractor_cost: Decimal = Field(default=Decimal("0"), ge=0)
    other_cost: Decimal = Field(default=Decimal("0"), ge=0)
    overhead_pct_override: Decimal | None = Field(default=None, ge=-100)
    risk_profit_pct_override: Decimal | None = Field(default=None, ge=-100)
    manual_sale_price: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    material_overrides: list[MaterialOverrideIn] = Field(default_factory=list)


class MaterialCalculationOut(BaseModel):
    material_id: int
    name: str
    article_number: str | None
    unit: str
    source_quantity: Decimal
    effective_quantity: Decimal
    source_purchase_price: Decimal
    effective_purchase_price: Decimal
    source_price_basis: Decimal
    effective_price_basis: Decimal
    waste_pct: Decimal
    base_cost: Decimal
    quantity_override: Decimal | None
    purchase_price_override: Decimal | None
    price_basis_override: Decimal | None


class ServiceCalculationOut(BaseModel):
    service_id: int
    external_id: str
    service_name: str
    unit: str

    source_site_time_raw: Decimal
    source_workshop_time_raw: Decimal
    source_sale_price: Decimal

    site_time_minutes: Decimal
    workshop_time_minutes: Decimal
    uses_source_site_time: bool
    uses_source_workshop_time: bool

    labor_rate: Decimal
    material_markup_pct: Decimal
    overhead_pct: Decimal
    risk_profit_pct: Decimal

    labor_amount: Decimal
    material_base_cost: Decimal
    material_markup_amount: Decimal
    material_amount: Decimal
    equipment_cost: Decimal
    subcontractor_cost: Decimal
    other_cost: Decimal
    subtotal_before_overhead: Decimal
    overhead_amount: Decimal
    subtotal_before_risk_profit: Decimal
    risk_profit_amount: Decimal
    calculated_sale_price: Decimal
    effective_sale_price: Decimal
    manual_sale_price: Decimal | None
    delta_to_source: Decimal
    delta_to_source_pct: Decimal | None
    notes: str | None

    labor_rate_override: Decimal | None
    material_markup_pct_override: Decimal | None
    overhead_pct_override: Decimal | None
    risk_profit_pct_override: Decimal | None

    materials: list[MaterialCalculationOut]


class CustomerExtraInfoCreate(BaseModel):
    info_type: str = Field(min_length=1, max_length=30)
    label: str | None = Field(default=None, max_length=120)
    value: str = Field(min_length=1)


class CustomerExtraInfoOut(CustomerExtraInfoCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CustomerCreate(BaseModel):
    customer_number: str | None = Field(default=None, max_length=50)
    salutation: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=80)
    first_name: str | None = Field(default=None, max_length=120)
    # last_name ist das eigentliche Pflichtfeld -- name (siehe CustomerOut) wird daraus
    # serverseitig zusammengesetzt und nicht mehr direkt entgegengenommen, siehe
    # CLAUDE.md "Adressimport aus dem Altsystem" für die Begründung dieser Aufteilung.
    last_name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="Privatkunde", min_length=1, max_length=80)
    contact_person: str | None = None
    street: str | None = None
    country: str = Field(default="Deutschland", max_length=120)
    postal_code: str | None = None
    city: str | None = None
    email: str | None = None
    email_2: str | None = None
    phone: str | None = None
    mobile: str | None = None
    fax: str | None = None
    notes: str | None = None
    default_payment_term_id: int | None = None
    extra_infos: list[CustomerExtraInfoCreate] = Field(default_factory=list)


class CustomerOut(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    customer_number: str
    extra_infos: list[CustomerExtraInfoOut] = Field(default_factory=list)


class CustomerUpdate(BaseModel):
    customer_number: str | None = Field(default=None, max_length=50)
    salutation: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=80)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="Privatkunde", min_length=1, max_length=80)
    contact_person: str | None = None
    street: str | None = None
    country: str = Field(default="Deutschland", max_length=120)
    postal_code: str | None = None
    city: str | None = None
    email: str | None = None
    email_2: str | None = None
    phone: str | None = None
    mobile: str | None = None
    fax: str | None = None
    notes: str | None = None
    default_payment_term_id: int | None = None


class CustomerExtraInfoUpdate(CustomerExtraInfoCreate):
    pass


class PropertyCreate(BaseModel):
    customer_id: int
    name: str = Field(min_length=1, max_length=255)
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    notes: str | None = None


class PropertyOut(PropertyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    # Read-only -- wird nie über das normale Objektformular gesetzt, siehe Property.is_primary_address.
    is_primary_address: bool = False


class PropertyUpdate(BaseModel):
    customer_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    notes: str | None = None


class ProjectCreate(BaseModel):
    customer_id: int
    property_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    status: str = "anfrage"
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None


class ProjectUpdate(BaseModel):
    customer_id: int
    property_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(default="anfrage", max_length=50)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None


class ProjectListOut(BaseModel):
    id: int
    project_number: str
    name: str
    status: str
    customer_id: int
    customer_name: str
    property_id: int | None
    property_name: str | None
    category: str | None = None
    quote_count: int
    order_count: int = 0
    document_count: int = 0
    archived: bool = False
    is_template: bool = False


class ProjectDuplicateRequest(BaseModel):
    as_template: bool = False


class ProjectDetailOut(ProjectListOut):
    description: str | None = None
    customer_number: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    property_street: str | None = None
    property_postal_code: str | None = None
    property_city: str | None = None
    document_count: int = 0


class ProjectDocumentOut(BaseModel):
    id: int
    project_id: int
    category: str
    subfolder: str | None = None
    original_filename: str
    content_type: str | None = None
    file_size: int
    description: str | None = None
    document_date: date | None = None
    uploaded_at: datetime
    is_image: bool = False
    can_preview: bool = False


class ProjectDocumentUpdate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    subfolder: str | None = Field(default=None, max_length=150)
    description: str | None = None
    document_date: date | None = None


class CustomerDocumentOut(BaseModel):
    id: int
    customer_id: int
    category: str
    subfolder: str | None = None
    original_filename: str
    content_type: str | None = None
    file_size: int
    description: str | None = None
    document_date: date | None = None
    uploaded_at: datetime
    is_image: bool = False
    can_preview: bool = False


class CustomerDocumentUpdate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    subfolder: str | None = Field(default=None, max_length=150)
    description: str | None = None
    document_date: date | None = None


class QuoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    vat_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100)
    intro_text: str | None = None
    outro_text: str | None = None


class QuoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    status: str = Field(default="entwurf", max_length=50)
    vat_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100)
    intro_text: str | None = None
    outro_text: str | None = None
    outro_text_2: str | None = None


class QuoteDocumentMetaUpdate(BaseModel):
    quote_date: date
    valid_until: date | None = None
    contact_person: str | None = Field(default=None, max_length=255)
    contact_person_employee_id: int | None = None
    payment_terms: str | None = None
    execution_period: str | None = Field(default=None, max_length=255)
    internal_note: str | None = None


class QuoteDocumentMetaOut(QuoteDocumentMetaUpdate):
    id: int
    quote_id: int


class QuoteSectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    parent_id: int | None = None


class QuoteSectionUpdate(QuoteSectionCreate):
    pass


class QuoteSectionOut(BaseModel):
    id: int
    quote_id: int
    parent_id: int | None
    title: str
    description: str | None
    sort_order: int
    section_number: str | None


class QuoteFreeItemCreate(BaseModel):
    short_text: str = Field(min_length=1)
    long_text: str = ""
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit: str = Field(default="Stück", min_length=1, max_length=50)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    position_type: str = Field(default="normal", max_length=30)
    section_id: int | None = None
    include_in_total: bool = True


class QuoteItemLayoutUpdate(BaseModel):
    section_id: int | None = None
    include_in_total: bool = True


class QuoteReorderSection(BaseModel):
    id: int
    parent_id: int | None = None
    sort_order: int


class QuoteReorderItem(BaseModel):
    id: int
    section_id: int | None = None
    sort_order: int


class QuoteReorderRequest(BaseModel):
    sections: list[QuoteReorderSection] = Field(default_factory=list)
    items: list[QuoteReorderItem] = Field(default_factory=list)


class QuoteItemCreate(BaseModel):
    service_id: int
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    section_id: int | None = None


class QuoteItemUpdate(BaseModel):
    quantity: Decimal = Field(gt=0)
    short_text: str = Field(min_length=1)
    long_text: str = ""
    unit: str = Field(min_length=1)
    unit_price: Decimal = Field(ge=0)
    position_type: str = "normal"
    gaeb_oz: str | None = None


class QuoteItemOut(BaseModel):
    id: int
    source_service_id: int | None
    source_external_id: str | None
    position_number: str
    gaeb_oz: str | None
    position_type: str
    short_text: str
    long_text: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    source_unit_price: Decimal | None
    line_total: Decimal
    has_project_calculation: bool = False
    section_id: int | None = None
    layout_sort_order: int = 10
    include_in_total: bool = True


class QuoteItemMaterialCalculationUpdate(BaseModel):
    id: int
    quantity: Decimal = Field(ge=0)
    waste_pct: Decimal = Field(default=Decimal("0"), ge=-100)
    purchase_price: Decimal = Field(ge=0)
    price_basis: Decimal = Field(default=Decimal("1"), gt=0)


class QuoteItemCalculationUpdate(BaseModel):
    site_time_minutes: Decimal = Field(ge=0)
    workshop_time_minutes: Decimal = Field(ge=0)
    labor_rate: Decimal = Field(ge=0)
    material_markup_pct: Decimal = Field(ge=-100)
    equipment_cost: Decimal = Field(default=Decimal("0"), ge=0)
    subcontractor_cost: Decimal = Field(default=Decimal("0"), ge=0)
    other_cost: Decimal = Field(default=Decimal("0"), ge=0)
    overhead_pct: Decimal = Field(ge=-100)
    risk_profit_pct: Decimal = Field(ge=-100)
    manual_sale_price: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    materials: list[QuoteItemMaterialCalculationUpdate] = Field(default_factory=list)


class QuoteItemMaterialCalculationOut(BaseModel):
    id: int
    source_material_id: int | None
    name: str
    article_number: str | None
    unit: str
    source_quantity: Decimal
    quantity: Decimal
    waste_pct: Decimal
    source_purchase_price: Decimal
    purchase_price: Decimal
    price_basis: Decimal
    effective_quantity: Decimal
    base_cost: Decimal


class QuoteItemCalculationOut(BaseModel):
    quote_item_id: int
    quote_id: int
    position_number: str
    service_external_id: str | None
    service_name: str
    unit: str
    site_time_minutes: Decimal
    workshop_time_minutes: Decimal
    labor_rate: Decimal
    material_markup_pct: Decimal
    equipment_cost: Decimal
    subcontractor_cost: Decimal
    other_cost: Decimal
    overhead_pct: Decimal
    risk_profit_pct: Decimal
    manual_sale_price: Decimal | None
    notes: str | None
    labor_amount: Decimal
    material_base_cost: Decimal
    material_markup_amount: Decimal
    material_amount: Decimal
    subtotal_before_overhead: Decimal
    overhead_amount: Decimal
    subtotal_before_risk_profit: Decimal
    risk_profit_amount: Decimal
    calculated_sale_price: Decimal
    effective_sale_price: Decimal
    materials: list[QuoteItemMaterialCalculationOut]


class QuoteOut(BaseModel):
    id: int
    quote_number: str
    project_id: int
    project_number: str
    project_name: str
    customer_id: int
    customer_name: str
    property_name: str | None
    title: str
    status: str
    vat_rate: Decimal
    intro_text: str | None
    outro_text: str | None
    outro_text_2: str | None = None
    tax_key_id: int | None = None
    tax_notice_text: str | None = None
    source_format: str
    gaeb_exchange_phase: str | None
    document_meta: QuoteDocumentMetaOut | None = None
    sections: list[QuoteSectionOut] = Field(default_factory=list)
    items: list[QuoteItemOut]
    net_total: Decimal
    optional_total: Decimal = Decimal("0")
    vat_total: Decimal
    gross_total: Decimal
    email_sent_at: datetime | None = None
    email_sent_to: str | None = None
    recipient_email: str | None = None  # aktuell hinterlegte Kunden-E-Mail, für die Versand-Oberfläche


class QuoteEmailSend(BaseModel):
    to_email: str | None = None  # None = automatisch aus Kundenstammdaten


class QuoteListOut(BaseModel):
    id: int
    quote_number: str
    project_id: int
    title: str
    status: str
    net_total: Decimal
    gross_total: Decimal


class InquiryCreate(BaseModel):
    customer_id: int
    property_id: int | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: str = Field(default="neu", max_length=50)
    priority: str = Field(default="normal", max_length=30)
    source: str = Field(default="sonstiges", max_length=80)
    contact_person: str | None = Field(default=None, max_length=255)
    assigned_to: str | None = Field(default=None, max_length=255)
    visit_at: datetime | None = None
    follow_up_at: datetime | None = None
    lost_reason: str | None = None


class InquiryUpdate(InquiryCreate):
    pass


class InquiryOut(BaseModel):
    id: int
    inquiry_number: str
    customer_id: int
    customer_name: str
    property_id: int | None
    property_name: str | None
    property_address: str | None
    project_id: int | None
    project_number: str | None
    title: str
    description: str | None
    status: str
    priority: str
    source: str
    contact_person: str | None
    assigned_to: str | None
    visit_at: datetime | None
    follow_up_at: datetime | None
    lost_reason: str | None
    created_at: datetime
    updated_at: datetime


class InquiryConvertRequest(BaseModel):
    project_name: str | None = Field(default=None, max_length=255)
    quote_title: str = Field(default="Angebot Dacharbeiten", min_length=1, max_length=255)
    create_quote: bool = True
    vat_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100)


class InquiryConvertOut(BaseModel):
    inquiry: InquiryOut
    project: ProjectListOut
    quote: QuoteOut | None = None


class GeneralSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    company_name: str
    managing_director: str | None
    street: str | None
    postal_code: str | None
    city: str | None
    country: str
    phone: str | None
    email: str | None
    website: str | None
    tax_number: str | None
    vat_id: str | None
    register_court: str | None
    register_number: str | None
    iban: str | None
    bic: str | None
    default_vat_rate: Decimal
    default_quote_intro: str | None
    default_quote_outro: str | None
    logo_filename: str | None
    sidebar_logo_height_px: int


class GeneralSettingsUpdate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    managing_director: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str = "Deutschland"
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    tax_number: str | None = None
    vat_id: str | None = None
    register_court: str | None = None
    register_number: str | None = None
    iban: str | None = None
    bic: str | None = None
    default_vat_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100)
    default_quote_intro: str | None = None
    default_quote_outro: str | None = None
    sidebar_logo_height_px: int = Field(default=48, ge=24, le=80)


class AppearanceSettingsOut(BaseModel):
    accent_color: str


class AppearanceSettingsUpdate(BaseModel):
    accent_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class NumberSequenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequence_key: str
    label: str
    format_pattern: str
    start_value: int
    next_value: int
    reset_yearly: bool
    preview: str | None = None


class NumberSequenceUpdate(BaseModel):
    format_pattern: str = Field(min_length=1, max_length=120)
    start_value: int = Field(ge=0)
    next_value: int = Field(ge=0)
    reset_yearly: bool = False


class NumberPreviewOut(BaseModel):
    sequence_key: str
    preview: str


class EmployeeFunctionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    employee_group: str = Field(default="gewerblich")
    description: str | None = None
    sort_order: int = Field(default=100, ge=0, le=9999)
    active: bool = True

    @model_validator(mode="after")
    def validate_group(self):
        if self.employee_group not in {"gewerblich", "kaufmaennisch"}:
            raise ValueError("Mitarbeitergruppe muss 'gewerblich' oder 'kaufmaennisch' sein.")
        return self


class EmployeeFunctionUpdate(EmployeeFunctionCreate):
    pass


class EmployeeFunctionOut(EmployeeFunctionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EmployeeCreate(BaseModel):
    employee_number: str | None = Field(default=None, max_length=50)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    # job_title bleibt für API-Abwärtskompatibilität bestehen; neue UI verwendet function_id.
    job_title: str | None = Field(default=None, max_length=160)
    function_id: int | None = None
    employee_group: str = Field(default="gewerblich")
    compensation_type: str = Field(default="hourly", pattern="^(hourly|fixed_salary)$")
    hourly_wage: Decimal | None = Field(default=None, ge=0)
    monthly_salary: Decimal | None = Field(default=None, ge=0)
    weekly_hours: Decimal = Field(default=Decimal("40.00"), gt=0, le=80)
    street: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=120)
    country: str = Field(default="Deutschland", max_length=120)
    phone: str | None = Field(default=None, max_length=80)
    mobile: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    birthday: date | None = None
    important_info: str | None = None
    available_as_caseworker: bool = False
    show_on_planning_board: bool = True
    cost_allocation: str | None = Field(default=None, pattern="^(labor_rate|variable_overhead|excluded)$")
    active: bool = True

    @model_validator(mode="after")
    def validate_commercial_wage(self):
        if self.employee_group not in {"gewerblich", "kaufmaennisch"}:
            raise ValueError("Mitarbeitergruppe muss 'gewerblich' oder 'kaufmaennisch' sein.")
        requires_cost = self.employee_group == "gewerblich" or self.cost_allocation in {"labor_rate", "variable_overhead"}
        if requires_cost:
            if self.compensation_type == "hourly" and (self.hourly_wage is None or self.hourly_wage <= 0):
                raise ValueError("Für Mitarbeiter, die in die Kalkulation einfließen, ist bei Stundenlohn ein positiver Stundenlohn erforderlich.")
            if self.compensation_type == "fixed_salary" and (self.monthly_salary is None or self.monthly_salary <= 0):
                raise ValueError("Für Mitarbeiter, die in die Kalkulation einfließen, ist bei Festgehalt ein positives Monatsbruttogehalt erforderlich.")
        return self


class EmployeeUpdate(EmployeeCreate):
    pass


class EmployeeOut(EmployeeCreate):
    id: int
    function_name: str | None = None
    effective_hourly_wage: Decimal | None = None
    annual_gross_wage: Decimal | None = None


class LaborRateSettingsOut(BaseModel):
    employer_cost_pct: Decimal
    productive_time_pct: Decimal
    annual_overhead: Decimal
    fixed_overhead_mode: str = "eur"
    fixed_overhead_value: Decimal = Decimal("0")
    variable_overhead_mode: str = "eur"
    variable_overhead_value: Decimal = Decimal("0")
    target_profit_pct: Decimal
    weeks_per_year: Decimal


class LaborRateSettingsUpdate(BaseModel):
    employer_cost_pct: Decimal = Field(ge=0, le=200)
    productive_time_pct: Decimal = Field(gt=0, le=100)
    # Legacy-Feld bleibt optional für ältere Clients; wird als fixe GK in EUR interpretiert.
    annual_overhead: Decimal | None = Field(default=None, ge=0)
    fixed_overhead_mode: str | None = Field(default=None, pattern="^(eur|pct)$")
    fixed_overhead_value: Decimal | None = Field(default=None, ge=0)
    variable_overhead_mode: str | None = Field(default=None, pattern="^(eur|pct)$")
    variable_overhead_value: Decimal | None = Field(default=None, ge=0)
    target_profit_pct: Decimal = Field(ge=0, le=200)
    weeks_per_year: Decimal = Field(default=Decimal("52.00"), gt=0, le=53)


class LaborRateCalculationOut(BaseModel):
    commercial_employee_count: int
    direct_employee_count: int = 0
    variable_overhead_employee_count: int = 0
    weighted_mean_wage: Decimal | None
    annual_paid_hours: Decimal
    annual_productive_hours: Decimal
    annual_gross_wages: Decimal
    annual_employer_costs: Decimal
    direct_labor_annual_cost: Decimal = Decimal("0")
    variable_employee_gross_wages: Decimal = Decimal("0")
    variable_employee_employer_costs: Decimal = Decimal("0")
    variable_employee_costs: Decimal = Decimal("0")
    labor_cost_per_productive_hour: Decimal | None
    fixed_overhead_annual: Decimal = Decimal("0")
    fixed_overhead_per_productive_hour: Decimal | None = None
    manual_variable_overhead_annual: Decimal = Decimal("0")
    variable_overhead_annual: Decimal = Decimal("0")
    variable_overhead_per_productive_hour: Decimal | None = None
    total_overhead_annual: Decimal = Decimal("0")
    overhead_per_productive_hour: Decimal | None
    self_cost_per_hour: Decimal | None
    target_profit_per_hour: Decimal | None
    suggested_labor_rate: Decimal | None
    current_labor_rate: Decimal
    difference_to_current: Decimal | None
    can_calculate: bool
    note: str | None = None


class SettingOptionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=180)
    value: str = Field(min_length=1)
    sort_order: int = Field(default=100, ge=0, le=99999)
    active: bool = True
    is_default: bool = False


class SettingOptionUpdate(SettingOptionCreate):
    pass


class SettingOptionOut(SettingOptionCreate):
    id: int
    group_key: str


class SettingOptionGroupOut(BaseModel):
    id: int
    group_key: str
    label: str
    description: str | None
    sort_order: int
    options: list[SettingOptionOut] = Field(default_factory=list)


class AppUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=160)
    employee_id: int | None = None
    role: str = Field(default="user", pattern="^(admin|user)$")
    active: bool = True


class AppUserUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=160)
    employee_id: int | None = None
    role: str = Field(default="user", pattern="^(admin|user)$")
    active: bool = True
    new_password: str | None = Field(default=None, min_length=8, max_length=200)


class AppUserOut(BaseModel):
    id: int
    username: str
    display_name: str
    employee_id: int | None = None
    role: str
    active: bool
    created_at: datetime
    last_login_at: datetime | None = None
    two_factor_configured: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class TwoFactorCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurred_at: datetime
    actor_user_id: int | None = None
    actor_name: str
    action: str
    entity_type: str
    entity_id: str | None = None
    entity_label: str | None = None
    project_id: int | None = None
    field_name: str | None = None
    field_label: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    details: str | None = None


class OrderCreateFromQuote(BaseModel):
    order_date: date = Field(default_factory=date.today)
    execution_start: date | None = None
    execution_end: date | None = None
    caseworker_employee_id: int | None = None
    project_manager_employee_id: int | None = None
    payment_terms: str | None = None
    remarks: str | None = None
    status: str = Field(default="beauftragt", max_length=50)


class OrderUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    status: str = Field(default="beauftragt", max_length=50)
    order_date: date
    execution_start: date | None = None
    execution_end: date | None = None
    caseworker_employee_id: int | None = None
    project_manager_employee_id: int | None = None
    payment_terms: str | None = None
    remarks: str | None = None
    intro_text: str | None = None
    outro_text: str | None = None
    outro_text_2: str | None = None


class OrderSectionOut(BaseModel):
    id: int
    parent_id: int | None
    title: str
    description: str | None
    sort_order: int
    section_number: str | None


class OrderItemOut(BaseModel):
    id: int
    section_id: int | None
    source_quote_item_id: int | None
    sort_order: int
    position_number: str
    gaeb_oz: str | None
    position_type: str
    source_external_id: str | None
    short_text: str
    long_text: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    include_in_total: bool
    line_total: Decimal


class OrderItemUpdate(BaseModel):
    quantity: Decimal = Field(ge=0)
    unit: str = Field(min_length=1, max_length=50)
    unit_price: Decimal = Field(ge=0)
    short_text: str = Field(min_length=1)
    long_text: str = ""
    position_type: str = Field(default="normal", max_length=30)
    gaeb_oz: str | None = Field(default=None, max_length=100)
    include_in_total: bool = True


class OrderSectionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class OrderSyncRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class OrderRevisionCreate(BaseModel):
    reason: str = Field(default="Auftragsstand manuell gesichert", min_length=1, max_length=255)


class OrderRevisionOut(BaseModel):
    id: int
    order_id: int
    revision_number: int
    reason: str
    source: str
    created_by_name: str
    created_at: datetime


class OrderOut(BaseModel):
    id: int
    order_number: str
    project_id: int
    project_number: str
    project_name: str
    source_quote_id: int
    quote_number_snapshot: str
    title: str
    status: str
    vat_rate: Decimal
    intro_text: str | None
    outro_text: str | None
    outro_text_2: str | None = None
    tax_key_id: int | None = None
    tax_notice_text: str | None = None
    customer_id: int | None = None
    customer_name: str
    customer_number: str | None
    customer_address: str | None
    property_name: str | None
    property_address: str | None
    order_date: date
    execution_start: date | None
    execution_end: date | None
    payment_terms: str | None
    remarks: str | None
    caseworker_employee_id: int | None
    caseworker_name: str | None
    project_manager_employee_id: int | None
    project_manager_name: str | None
    sections: list[OrderSectionOut] = Field(default_factory=list)
    items: list[OrderItemOut] = Field(default_factory=list)
    net_total: Decimal
    optional_total: Decimal = Decimal("0")
    vat_total: Decimal
    gross_total: Decimal
    source_quote_in_sync: bool | None = None
    invoiced_net: Decimal | None = None
    invoiced_gross: Decimal | None = None
    open_net: Decimal | None = None
    open_gross: Decimal | None = None
    revision_count: int = 0
    current_revision_number: int = 0
    created_at: datetime
    email_sent_at: datetime | None = None
    email_sent_to: str | None = None
    recipient_email: str | None = None  # aktuell hinterlegte Kunden-E-Mail, für die Versand-Oberfläche


class OrderEmailSend(BaseModel):
    to_email: str | None = None  # None = automatisch aus Kundenstammdaten


class TaxKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    vat_rate: Decimal
    notice_text: str | None
    is_default: bool
    archived: bool


class ChangelogEntryOut(BaseModel):
    version: str
    title: str
    html: str


class ReminderLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    level: int
    label: str
    days_after_previous_step: int
    fee_amount: Decimal
    text_template: str | None
    email_subject_template: str | None
    email_body_template: str | None
    active: bool


class ReminderLevelUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    days_after_previous_step: int = Field(ge=1, le=365)
    fee_amount: Decimal = Field(ge=0)
    text_template: str | None = None
    email_subject_template: str | None = None
    email_body_template: str | None = None
    active: bool = True


class ReminderCreate(BaseModel):
    level: int = Field(ge=1, le=3)


class ReminderUpdate(BaseModel):
    text: str | None = None
    fee_amount: Decimal = Field(ge=0)
    new_due_date: date | None = None


class ReminderOut(BaseModel):
    id: int
    reminder_number: str | None
    invoice_id: int
    invoice_number: str | None
    order_id: int
    level: int
    status: str
    reminder_date: date
    new_due_date: date | None
    outstanding_amount: Decimal
    fee_amount: Decimal
    total_amount: Decimal
    text: str | None
    formatted_text: str
    customer_name: str
    email_sent_at: datetime | None = None
    email_sent_to: str | None = None
    recipient_email: str | None = None  # aktuell hinterlegte Kunden-E-Mail, für die Versand-Oberfläche


class ReminderStatusOut(BaseModel):
    current_level: int
    next_level: int | None
    next_due_on: date | None
    is_due_now: bool
    draft: ReminderOut | None = None


class InvoiceNeedingAttentionOut(BaseModel):
    invoice_id: int
    invoice_number: str | None
    order_id: int
    customer_name: str
    due_date: date
    outstanding_amount: Decimal
    caseworker_employee_id: int | None = None
    current_level: int
    next_level: int | None
    next_due_on: date | None
    is_due_now: bool
    draft: ReminderOut | None = None


class ReminderSettingsOut(BaseModel):
    auto_create_drafts: bool


class ReminderSettingsUpdate(BaseModel):
    auto_create_drafts: bool


class SmtpSettingsOut(BaseModel):
    configured: bool
    send_method: str  # 'smtp' | 'graph_oauth2'
    host: str | None
    port: int
    username: str | None
    encryption: str
    sender_email: str | None
    sender_name: str | None
    has_password: bool  # niemals das Passwort selbst -- nur ob eines hinterlegt ist
    graph_tenant_id: str | None
    graph_client_id: str | None
    graph_sender_mailbox: str | None
    has_graph_client_secret: bool  # niemals das Secret selbst


class SmtpSettingsUpdate(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str = Field(min_length=1, max_length=255)
    encryption: str = Field(pattern="^(starttls|ssl|none)$")
    sender_email: str = Field(min_length=3, max_length=255)
    sender_name: str | None = None
    password: str | None = None  # None = unverändert lassen


class GraphSettingsUpdate(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=255)
    client_id: str = Field(min_length=1, max_length=255)
    sender_mailbox: str = Field(min_length=3, max_length=255)
    client_secret: str | None = None  # None = unverändert lassen


class SendMethodUpdate(BaseModel):
    send_method: str = Field(pattern="^(smtp|graph_oauth2)$")


class ReminderEmailSend(BaseModel):
    to_email: str | None = None  # None = automatisch aus Kundenstammdaten


class TaxKeyCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    vat_rate: Decimal = Field(ge=0, le=100)
    notice_text: str | None = None


class TaxKeyUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    vat_rate: Decimal = Field(ge=0, le=100)
    notice_text: str | None = None


class PaymentTermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    days: int
    skonto_percent: Decimal | None
    skonto_days: int | None
    text_template: str | None
    is_default: bool
    archived: bool


class PaymentTermCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    days: int = Field(ge=0)
    skonto_percent: Decimal | None = Field(default=None, gt=0, le=100)
    skonto_days: int | None = Field(default=None, ge=0)
    text_template: str | None = None


class PaymentTermUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    days: int = Field(ge=0)
    skonto_percent: Decimal | None = Field(default=None, gt=0, le=100)
    skonto_days: int | None = Field(default=None, ge=0)
    text_template: str | None = None


class InvoiceItemOut(BaseModel):
    id: int
    source_order_item_id: int | None
    sort_order: int
    position_number: str
    gaeb_oz: str | None
    short_text: str
    long_text: str
    unit: str
    unit_price: Decimal
    soll_quantity: Decimal | None
    ist_quantity: Decimal
    billed_quantity: Decimal
    billed_total: Decimal


class InvoiceOut(BaseModel):
    id: int
    invoice_number: str | None
    order_id: int
    order_number: str
    project_id: int
    project_number: str
    customer_id: int
    invoice_type: str
    status: str
    invoice_date: date
    due_date: date | None
    paid_date: date | None
    storno_of_invoice_id: int | None
    customer_name: str
    customer_number: str | None
    customer_address: str | None
    property_name: str | None
    property_address: str | None
    vat_rate: Decimal
    lump_sum_net: Decimal | None
    progress_description: str | None
    intro_text: str | None
    outro_text: str | None
    outro_text_2: str | None = None
    payment_terms: str | None
    tax_key_id: int | None = None
    tax_notice_text: str | None = None
    skonto_percent: Decimal | None
    skonto_days: int | None
    payment_terms_sentence: str
    is_editable: bool
    is_overdue: bool
    items: list[InvoiceItemOut] = Field(default_factory=list)
    net_total: Decimal
    vat_total: Decimal
    gross_total: Decimal
    email_sent_at: datetime | None = None
    email_sent_to: str | None = None
    recipient_email: str | None = None  # aktuell hinterlegte Kunden-E-Mail, für die Versand-Oberfläche
    # Seit 1.2.23: nur vom POST .../invoices/aus-zeitbuchungen-Endpunkt gesetzt, wenn Katalog-
    # Materialpositionen ohne konfigurierten Aufschlag (material_markup_pct == 0) entstanden
    # sind -- für jeden anderen Rechnungstyp/-abruf bleibt es None. Kein persistiertes Feld,
    # reines Ergebnis-Feedback dieses einen Rechnungslaufs.
    material_markup_hint: str | None = None


class InvoiceEmailSend(BaseModel):
    to_email: str | None = None  # None = automatisch aus Kundenstammdaten


class DocumentEmailTemplateOut(BaseModel):
    document_type: str
    subject_template: str | None
    body_template: str | None


class DocumentEmailTemplateUpdate(BaseModel):
    subject_template: str | None = None
    body_template: str | None = None


class InvoiceListOut(BaseModel):
    id: int
    invoice_number: str | None
    invoice_type: str
    status: str
    invoice_date: date
    due_date: date | None
    is_overdue: bool
    net_total: Decimal
    gross_total: Decimal


class InvoiceOverviewOut(BaseModel):
    id: int
    invoice_number: str | None
    invoice_type: str
    status: str
    invoice_date: date
    due_date: date | None
    is_overdue: bool
    customer_name: str
    order_id: int
    order_number: str | None
    project_number: str | None
    gross_total: Decimal


class InvoiceCreateAbschlagPauschal(BaseModel):
    lump_sum_net: Decimal = Field(gt=0)
    progress_description: str | None = None
    due_date: date | None = None


class InvoiceCreateFromOrder(BaseModel):
    due_date: date | None = None


class InvoiceHeaderUpdate(BaseModel):
    due_date: date | None = None
    progress_description: str | None = None
    lump_sum_net: Decimal | None = Field(default=None, gt=0)
    intro_text: str | None = None
    outro_text: str | None = None
    outro_text_2: str | None = None
    payment_terms: str | None = None


class InvoiceItemCreate(BaseModel):
    short_text: str = Field(min_length=1)
    long_text: str = ""
    unit: str = Field(min_length=1, max_length=50)
    unit_price: Decimal = Field(ge=0)
    ist_quantity: Decimal = Field(ge=0)
    source_order_item_id: int | None = None
    soll_quantity: Decimal | None = None
    position_number: str | None = None


class InvoiceItemUpdate(BaseModel):
    short_text: str | None = None
    long_text: str | None = None
    unit: str | None = None
    unit_price: Decimal | None = Field(default=None, ge=0)
    ist_quantity: Decimal | None = Field(default=None, ge=0)


class InvoiceMarkPaid(BaseModel):
    paid_date: date | None = None


class InvoicePaymentTermUpdate(BaseModel):
    payment_term_id: int


class TaxKeySelection(BaseModel):
    tax_key_id: int


class OrderListOut(BaseModel):
    id: int
    order_number: str
    project_id: int
    project_number: str
    project_name: str
    customer_name: str
    title: str
    status: str
    order_date: date
    net_total: Decimal
    gross_total: Decimal
    invoice_count: int = 0
    fully_invoiced: bool = False
    invoiced_net: Decimal = Decimal("0")
    invoiced_gross: Decimal = Decimal("0")
    planned_hours: Decimal = Decimal("0")
    service_report_count: int = 0


class WorkPreparationUpdate(BaseModel):
    status: str = Field(default="offen", max_length=50)
    planned_start: date | None = None
    planned_end: date | None = None
    site_notes: str | None = None
    material_notes: str | None = None


class WorkPreparationEmployeeCreate(BaseModel):
    employee_id: int
    role: str | None = Field(default=None, max_length=120)
    planned_hours: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class WorkPreparationEmployeeUpdate(BaseModel):
    role: str | None = Field(default=None, max_length=120)
    planned_hours: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class WorkPreparationTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    status: str = Field(default="offen", max_length=40)
    priority: str = Field(default="normal", max_length=30)
    due_date: date | None = None
    assigned_employee_id: int | None = None
    notes: str | None = None
    sort_order: int = 100


class WorkPreparationTaskUpdate(WorkPreparationTaskCreate):
    pass


class WorkPreparationMaterialUpdate(BaseModel):
    planned_quantity: Decimal = Field(ge=0)
    status: str = Field(default="bedarf", max_length=40)
    supplier: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class WorkPreparationEmployeeOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str | None
    role: str | None
    planned_hours: Decimal | None
    notes: str | None


class WorkPreparationTaskOut(BaseModel):
    id: int
    title: str
    status: str
    priority: str
    due_date: date | None
    assigned_employee_id: int | None
    assigned_employee_name: str | None
    notes: str | None
    sort_order: int


class WorkPreparationMaterialOut(BaseModel):
    id: int
    article_number: str | None
    name: str
    unit: str
    calculated_quantity: Decimal
    planned_quantity: Decimal
    status: str
    supplier_id: int | None = None
    supplier: str | None
    notes: str | None
    source_order_item_id: int | None
    source_position: str | None
    source_short_text: str | None
    delivery_notes: list[dict] = Field(default_factory=list)


class WorkPreparationOut(BaseModel):
    id: int
    order_id: int
    order_number: str
    project_id: int
    project_number: str
    project_name: str
    status: str
    planned_start: date | None
    planned_end: date | None
    site_notes: str | None
    material_notes: str | None
    planned_total_hours: Decimal
    actual_total_hours: Decimal = Decimal("0")
    actual_travel_hours: Decimal = Decimal("0")
    actual_all_hours: Decimal = Decimal("0")
    hours_variance: Decimal = Decimal("0")
    time_by_type: dict = Field(default_factory=dict)
    order_item_actual_hours: dict[str, Decimal] = Field(default_factory=dict)
    assigned_planned_hours: Decimal
    open_task_count: int
    material_count: int
    employees: list[WorkPreparationEmployeeOut] = Field(default_factory=list)
    teams: list[dict] = Field(default_factory=list)
    tasks: list[WorkPreparationTaskOut] = Field(default_factory=list)
    materials: list[WorkPreparationMaterialOut] = Field(default_factory=list)
    delivery_notes: list[dict] = Field(default_factory=list)

# --- Prototype 0.8.2: Ressourcen-, Team- und Lieferantenstammdaten ---
class SupplierCreate(BaseModel):
    supplier_number: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    contact_person: str | None = Field(default=None, max_length=255)
    street: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=120)
    country: str = Field(default="Deutschland", max_length=120)
    phone: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    customer_number_at_supplier: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    active: bool = True

class SupplierUpdate(SupplierCreate):
    pass

class SupplierOut(SupplierCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class OperationalResourceCreate(BaseModel):
    resource_number: str | None = Field(default=None, max_length=50)
    resource_type: str = Field(default="Maschine", max_length=50)
    name: str = Field(min_length=1, max_length=255)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    identifier: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    active: bool = True

class OperationalResourceUpdate(OperationalResourceCreate):
    pass

class OperationalResourceOut(OperationalResourceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TeamEmployeeInput(BaseModel):
    employee_id: int
    role: str | None = Field(default=None, max_length=120)

class TeamResourceInput(BaseModel):
    resource_id: int
    role: str | None = Field(default=None, max_length=120)

class TeamCreate(BaseModel):
    team_number: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    active: bool = True
    employees: list[TeamEmployeeInput] = Field(default_factory=list)
    resources: list[TeamResourceInput] = Field(default_factory=list)

class TeamUpdate(TeamCreate):
    pass

class TeamEmployeeOut(BaseModel):
    employee_id: int
    employee_name: str
    role: str | None = None

class TeamResourceOut(BaseModel):
    resource_id: int
    resource_name: str
    resource_type: str
    role: str | None = None

class TeamOut(BaseModel):
    id: int
    team_number: str | None
    name: str
    description: str | None
    active: bool
    employees: list[TeamEmployeeOut] = Field(default_factory=list)
    resources: list[TeamResourceOut] = Field(default_factory=list)


class WorkPreparationTeamAssign(BaseModel):
    team_id: int
    notes: str | None = None

class WorkPreparationMaterialUpdateV082(BaseModel):
    planned_quantity: Decimal = Field(ge=0)
    status: str = Field(default="bedarf", max_length=40)
    supplier_id: int | None = None
    supplier: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class WorkPreparationMaterialBulkAssign(BaseModel):
    material_ids: list[int] = Field(min_length=1)
    supplier_id: int | None = None
    delivery_note_id: int | None = None


class PlanningSlotCreate(BaseModel):
    order_id: int
    team_id: int
    start_date: date
    end_date: date
    status: str = Field(default="geplant", max_length=40)
    notes: str | None = None
    planned_hours: Decimal | None = Field(default=None, ge=0)
    travel_hours_per_employee_day: Decimal | None = Field(default=None, ge=0, lt=24)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
        return self


class PlanningSlotUpdate(BaseModel):
    team_id: int | None = None
    start_date: date
    end_date: date
    status: str = Field(default="geplant", max_length=40)
    notes: str | None = None
    planned_hours: Decimal | None = Field(default=None, ge=0)
    travel_hours_per_employee_day: Decimal | None = Field(default=None, ge=0, lt=24)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
        return self


class PlanningSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int = 1
    daily_work_hours: Decimal
    default_travel_hours_per_employee_day: Decimal
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    federal_state_code: str = "NW"
    federal_state_name: str | None = None
    auto_public_holidays: bool = True
    show_school_holidays: bool = True


class PlanningSettingsUpdate(BaseModel):
    daily_work_hours: Decimal = Field(gt=0, le=24)
    default_travel_hours_per_employee_day: Decimal = Field(ge=0, lt=24)
    monday: bool = True
    tuesday: bool = True
    wednesday: bool = True
    thursday: bool = True
    friday: bool = True
    saturday: bool = False
    sunday: bool = False
    federal_state_code: str = Field(default="NW", pattern="^(BW|BY|BE|BB|HB|HH|HE|MV|NI|NW|RP|SL|SN|ST|SH|TH)$")
    auto_public_holidays: bool = True
    show_school_holidays: bool = True

    @model_validator(mode="after")
    def validate_capacity(self):
        if self.default_travel_hours_per_employee_day >= self.daily_work_hours:
            raise ValueError("Die Standard-Anfahrtszeit muss kleiner als die tägliche Arbeitszeit sein.")
        if not any([self.monday,self.tuesday,self.wednesday,self.thursday,self.friday,self.saturday,self.sunday]):
            raise ValueError("Mindestens ein Arbeitstag pro Woche muss aktiviert sein.")
        return self


class PlanningHolidayCreate(BaseModel):
    holiday_date: date
    name: str = Field(min_length=1, max_length=180)
    active: bool = True


class PlanningHolidayOut(PlanningHolidayCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EmployeeAbsenceCreate(BaseModel):
    employee_id: int
    absence_type: str = Field(default="Urlaub", min_length=1, max_length=80)
    start_date: date
    end_date: date
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
        return self


class EmployeeAbsenceOut(EmployeeAbsenceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_name: str | None = None


# --- Version 1.0.2: Abwesenheitsanträge ---
class EmployeeAbsenceRequestCreate(BaseModel):
    employee_id: int
    absence_type: str = Field(default="Urlaub", min_length=1, max_length=80)
    start_date: date
    end_date: date
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
        return self


class EmployeeAbsenceRequestReview(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    review_notes: str | None = None


class EmployeeAbsenceRequestOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    absence_type: str
    start_date: date
    end_date: date
    notes: str | None = None
    status: str
    requested_by_user_id: int | None = None
    reviewed_by_user_id: int | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    approved_absence_id: int | None = None
    created_at: datetime


class PlanningSuggestionRequest(BaseModel):
    order_id: int
    team_id: int
    start_date: date
    daily_work_hours: Decimal | None = Field(default=None, gt=0, le=24)
    travel_hours_per_employee_day: Decimal | None = Field(default=None, ge=0, lt=24)


class PlanningSlotCapacityUpdate(BaseModel):
    planned_hours: Decimal | None = Field(default=None, ge=0)
    travel_hours_per_employee_day: Decimal | None = Field(default=None, ge=0, lt=24)


# --- Version 1.0: Zeiterfassung / mobile Baustellenansicht ---
class TimeEntryManualCreate(BaseModel):
    employee_id: int
    order_id: int
    order_item_id: int | None = None
    work_date: date
    entry_type: str = Field(default="site", max_length=40)
    activity: str | None = Field(default=None, max_length=180)
    hours: Decimal = Field(gt=0, le=24)
    break_minutes: int = Field(default=0, ge=0, le=720)
    notes: str | None = None

class TimeEntryUpdate(TimeEntryManualCreate):
    pass

class TimeTimerStart(BaseModel):
    employee_id: int
    order_id: int
    order_item_id: int | None = None
    entry_type: str = Field(default="site", max_length=40)
    activity: str | None = Field(default=None, max_length=180)
    notes: str | None = None
    started_at: datetime | None = None

class TimeTimerStop(BaseModel):
    ended_at: datetime | None = None
    break_minutes: int = Field(default=0, ge=0, le=720)

class TimeGroupManualCreate(BaseModel):
    employee_ids: list[int] = Field(min_length=1)
    team_id: int | None = None
    order_id: int
    order_item_id: int | None = None
    work_date: date
    entry_type: str = Field(default="site", max_length=40)
    activity: str | None = Field(default=None, max_length=180)
    hours: Decimal = Field(gt=0, le=24)
    break_minutes: int = Field(default=0, ge=0, le=720)
    notes: str | None = None


class TimeGroupTimerStart(BaseModel):
    employee_ids: list[int] = Field(min_length=1)
    team_id: int | None = None
    order_id: int
    order_item_id: int | None = None
    entry_type: str = Field(default="site", max_length=40)
    activity: str | None = Field(default=None, max_length=180)
    notes: str | None = None
    started_at: datetime | None = None


class TimeGroupTimerStop(BaseModel):
    ended_at: datetime | None = None
    break_minutes: int = Field(default=0, ge=0, le=720)


class TimeGroupOut(BaseModel):
    id: int
    initiated_by_employee_id: int | None = None
    team_id: int | None = None
    order_id: int
    project_id: int
    order_item_id: int | None = None
    mode: str
    entry_type: str
    activity: str | None = None
    work_date: date
    started_at: datetime | None = None
    ended_at: datetime | None = None
    break_minutes: int
    hours: Decimal
    notes: str | None = None
    status: str
    member_entries: list[dict] = Field(default_factory=list)


class TimeEntryOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    project_id: int
    project_number: str | None = None
    project_name: str | None = None
    order_id: int
    order_number: str | None = None
    order_title: str | None = None
    order_item_id: int | None = None
    order_item_oz: str | None = None
    order_item_text: str | None = None
    work_date: date
    entry_type: str
    counts_as_productive: bool
    activity: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    break_minutes: int
    hours: Decimal
    notes: str | None = None
    source: str
    status: str
    created_at: datetime

class TimeTrackingSettingsOut(BaseModel):
    rounding_minutes: int = 0
    default_break_minutes: int = 0
    allow_manual_entries: bool = True
    allow_group_bookings: bool = True
    require_order_item: bool = False
    require_activity: bool = False
    datev_target: str = "lohn_gehalt"
    datev_wage_type_site: str | None = None
    datev_wage_type_travel: str | None = None
    datev_wage_type_workshop: str | None = None
    datev_wage_type_other: str | None = None
    datev_personnel_equals_erp_number: bool = False
    default_work_time_model_id: int | None = None


class TimeTrackingSettingsUpdate(TimeTrackingSettingsOut):
    @model_validator(mode="after")
    def validate_values(self):
        if self.rounding_minutes not in {0, 5, 10, 15, 30}:
            raise ValueError("Rundung muss 0, 5, 10, 15 oder 30 Minuten betragen.")
        if self.default_break_minutes < 0 or self.default_break_minutes > 240:
            raise ValueError("Standardpause muss zwischen 0 und 240 Minuten liegen.")
        if self.datev_target not in {"lohn_gehalt", "lodas"}:
            raise ValueError("DATEV-Ziel muss Lohn und Gehalt oder LODAS sein.")
        return self


class EmployeePayrollSettingsUpdate(BaseModel):
    datev_personnel_number: str | None = Field(default=None, max_length=30)
    payroll_export_enabled: bool = True


# --- Version 1.2.14: Dachflächen und Bauteile ---
class RoofAreaOut(BaseModel):
    id: int
    property_id: int
    property_name: str | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    name: str
    roof_type: str | None = None
    covering: str | None = None
    pitch_degrees: Decimal | None = None
    area_sqm: Decimal | None = None
    build_up: str | None = None
    insulation: str | None = None
    last_renovation: date | None = None
    contractor: str | None = None
    warranty_until: date | None = None
    has_sketch: bool
    notes: str | None = None
    archived: bool
    component_count: int
    created_at: datetime
    updated_at: datetime


class RoofAreaCreate(BaseModel):
    # Seit 1.2.18 OHNE build_up/insulation -- siehe RoofAreaOut/app/models.py::RoofArea für die
    # Begründung (Schichtenliste RoofLayer hat das Freitextfeld abgelöst).
    property_id: int
    name: str = Field(min_length=1, max_length=255)
    roof_type: str | None = None
    covering: str | None = None
    pitch_degrees: Decimal | None = None
    area_sqm: Decimal | None = None
    last_renovation: date | None = None
    contractor: str | None = None
    warranty_until: date | None = None
    notes: str | None = None


class RoofAreaUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    roof_type: str | None = None
    covering: str | None = None
    pitch_degrees: Decimal | None = None
    area_sqm: Decimal | None = None
    last_renovation: date | None = None
    contractor: str | None = None
    warranty_until: date | None = None
    notes: str | None = None


class RoofAreaBulkCreate(BaseModel):
    roof_type: str | None = None
    names: list[str] = Field(min_length=1)


class RoofComponentOut(BaseModel):
    id: int
    roof_area_id: int
    component_type: str | None = None
    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    year_built: int | None = None
    sketch_x: Decimal | None = None
    sketch_y: Decimal | None = None
    sort_order: int
    notes: str | None = None
    archived: bool
    finding_count: int = 0
    created_at: datetime
    updated_at: datetime


class RoofComponentCreate(BaseModel):
    component_type: str | None = None
    name: str = Field(min_length=1, max_length=255)
    quantity: Decimal | None = None
    unit: str | None = None
    year_built: int | None = None
    sort_order: int = 100
    notes: str | None = None


class RoofComponentUpdate(BaseModel):
    component_type: str | None = None
    name: str = Field(min_length=1, max_length=255)
    quantity: Decimal | None = None
    unit: str | None = None
    year_built: int | None = None
    sort_order: int = 100
    notes: str | None = None


class RoofComponentPositionUpdate(BaseModel):
    sketch_x: Decimal = Field(ge=0, le=100)
    sketch_y: Decimal = Field(ge=0, le=100)
    sketch_w: Decimal | None = Field(default=None, ge=0, le=100)
    sketch_h: Decimal | None = Field(default=None, ge=0, le=100)


# --- Version 1.2.18: Dachaufbau als Schichtenliste ---
class RoofLayerTypeOut(BaseModel):
    id: int
    key: str
    label: str
    roof_type: str | None = None
    option_group: str | None = None
    has_execution: bool
    has_thickness: bool
    has_notes: bool
    sort_order: int
    active: bool


class RoofLayerTypeCreate(BaseModel):
    key: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=120)
    roof_type: str | None = None
    option_group: str | None = None
    has_execution: bool = True
    has_thickness: bool = False
    has_notes: bool = True


class RoofLayerTypeUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    roof_type: str | None = None
    option_group: str | None = None
    has_execution: bool = True
    has_thickness: bool = False
    has_notes: bool = True


class LayerTypeReorder(BaseModel):
    roof_type: str | None = None
    ordered_ids: list[int]


class RoofLayerOut(BaseModel):
    id: int
    roof_area_id: int
    layer_type_id: int
    layer_type_key: str | None = None
    layer_type_label: str | None = None
    layer_type_roof_type: str | None = None
    layer_type_option_group: str | None = None
    layer_type_has_execution: bool = True
    layer_type_has_thickness: bool = False
    layer_type_has_notes: bool = True
    present: bool
    execution: str | None = None
    thickness_mm: int | None = None
    notes: str | None = None


class RoofLayerUpsert(BaseModel):
    present: bool | None = None
    execution: str | None = None
    thickness_mm: int | None = None
    notes: str | None = None


# --- Version 1.2.19: Bauteilarten als echte Tabelle (vorher SettingOptionGroup) ---
class RoofComponentTypeOut(BaseModel):
    id: int
    key: str
    label: str
    is_area: bool
    sort_order: int
    active: bool


class RoofComponentTypeCreate(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    is_area: bool = False


class RoofComponentTypeUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    is_area: bool = False


class ComponentTypeReorder(BaseModel):
    ordered_ids: list[int]


class EmployeePayrollSettingsOut(EmployeePayrollSettingsUpdate):
    employee_id: int
    employee_name: str
    employee_number: str | None = None




class WorkTimeBreakRuleInput(BaseModel):
    id: int | None = None
    threshold_hours: Decimal = Field(gt=0, le=24)
    break_minutes: int = Field(ge=0, le=720)
    sort_order: int = 100


class WorkTimeModelUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=50)
    daily_target_hours: Decimal = Field(default=Decimal("8.00"), gt=0, le=24)
    valid_from_week: int = Field(default=1, ge=1, le=53)
    valid_to_week: int = Field(default=53, ge=1, le=53)
    description: str | None = None
    active: bool = True
    sort_order: int = 100
    break_rules: list[WorkTimeBreakRuleInput] = Field(default_factory=list)


class EmployeeWorkTimeModelUpdate(BaseModel):
    model_id: int


class EmployeeWorkTimeModelBulkUpdate(BaseModel):
    employee_ids: list[int] = Field(min_length=1)
    model_id: int


class TimeBackofficeBulkAction(BaseModel):
    entry_ids: list[int] = Field(default_factory=list)
    action: str = Field(pattern="^(delete)$")


class ServiceMaterialAdd(BaseModel):
    material_id: int
    quantity: Decimal = Field(gt=0)
    waste_pct: Decimal = Field(default=Decimal("0"), ge=-100)


class ServiceCreate(BaseModel):
    catalog_id: int | None = None
    service_type: str | None = None
    short_text: str = Field(min_length=1)
    long_text: str | None = None
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=50)
    sale_price: Decimal | None = Field(default=None, ge=0)
    site_time_raw: Decimal = Field(default=Decimal("0"), ge=0)
    workshop_time_raw: Decimal = Field(default=Decimal("0"), ge=0)
    labor_rate_override: Decimal | None = Field(default=None, ge=0)
    material_markup_pct_override: Decimal | None = Field(default=None, ge=-100)
    equipment_cost: Decimal = Field(default=Decimal("0"), ge=0)
    subcontractor_cost: Decimal = Field(default=Decimal("0"), ge=0)
    other_cost: Decimal = Field(default=Decimal("0"), ge=0)
    overhead_pct_override: Decimal | None = Field(default=None, ge=-100)
    risk_profit_pct_override: Decimal | None = Field(default=None, ge=-100)
    materials: list[ServiceMaterialAdd] = Field(default_factory=list)


class ServiceBaseUpdate(BaseModel):
    service_type: str | None = None
    short_text: str = Field(min_length=1)
    long_text: str | None = None
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=50)


class ServiceMoveOrCopy(BaseModel):
    catalog_id: int | None = None


class MaterialCatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    article_number: str | None
    name: str
    unit: str
    purchase_price: Decimal
    price_basis: Decimal
    source: str
    catalog_id: int | None
    created_at: datetime


class MaterialCatalogCreate(BaseModel):
    article_number: str | None = None
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1, max_length=50)
    purchase_price: Decimal = Field(ge=0)
    price_basis: Decimal = Field(default=Decimal("1"), gt=0)
    catalog_id: int | None = None


class MaterialCatalogUpdate(BaseModel):
    article_number: str | None = None
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1, max_length=50)
    purchase_price: Decimal = Field(ge=0)
    price_basis: Decimal = Field(default=Decimal("1"), gt=0)


class MaterialGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    is_import_catalog: bool
    archived: bool
    created_at: datetime


class MaterialGroupCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class MaterialMoveOrCopy(BaseModel):
    catalog_id: int | None = None


class CatalogCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class CatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    is_import_catalog: bool
    archived: bool
    created_at: datetime


class DocumentLayoutBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_type: str
    block_type: str
    label: str
    x_mm: Decimal
    y_mm: Decimal
    width_mm: Decimal
    height_mm: Decimal
    content: str | None
    font_size: Decimal
    font_weight: str
    text_align: str
    visible: bool
    sort_order: int


class DocumentLayoutBlockUpdate(BaseModel):
    x_mm: Decimal = Field(ge=0, le=210)
    y_mm: Decimal = Field(ge=0, le=297)
    width_mm: Decimal = Field(gt=0, le=210)
    height_mm: Decimal = Field(gt=0, le=297)
    content: str | None = None
    font_size: Decimal = Field(ge=5, le=36)
    font_weight: str = Field(pattern="^(normal|bold)$")
    text_align: str = Field(pattern="^(left|center|right)$")
    visible: bool = True


class DocumentPageMarginsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_type: str
    page_type: str
    top_mm: Decimal
    bottom_mm: Decimal
    left_mm: Decimal
    right_mm: Decimal


class DocumentPageMarginsUpdate(BaseModel):
    top_mm: Decimal = Field(ge=0, le=100)
    bottom_mm: Decimal = Field(ge=0, le=100)
    left_mm: Decimal = Field(ge=0, le=100)
    right_mm: Decimal = Field(ge=0, le=100)


class DocumentLayoutBackgroundOut(BaseModel):
    document_type: str
    has_background: bool
    repeat_on_every_page: bool = True


# --- Version 1.0.102: Dashboard-Widgets ---
class DashboardWidgetOut(BaseModel):
    widget_key: str
    sort_order: int
    visible: bool


class DashboardWidgetItem(BaseModel):
    widget_key: str = Field(min_length=1, max_length=60)
    sort_order: int = 100
    visible: bool = True


class DashboardWidgetLayoutUpdate(BaseModel):
    widgets: list[DashboardWidgetItem] = Field(default_factory=list)


# --- Version 1.0.103: Modul-Umschalter ---
class ModuleStateOut(BaseModel):
    module_key: str
    label: str
    enabled: bool


class ModuleStateUpdate(BaseModel):
    enabled: bool


# --- Version 1.1.0: Aufgabenmanagement ---
class TaskChecklistItemOut(BaseModel):
    id: int
    title: str
    done: bool


class TaskOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: str
    status_label: str
    status_is_done: bool
    priority: str
    due_date: date | None = None
    assigned_employee_id: int | None = None
    assigned_employee_name: str | None = None
    project_id: int | None = None
    project_number: str | None = None
    project_name: str | None = None
    created_by_user_id: int | None = None
    source_module: str | None = None
    source_label: str | None = None
    source_url: str | None = None
    archived: bool
    checklist_items: list[TaskChecklistItemOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    priority: str = "normal"
    due_date: date | None = None
    assigned_employee_id: int | None = None
    project_id: int | None = None


class TaskUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: str
    priority: str
    due_date: date | None = None
    assigned_employee_id: int | None = None
    project_id: int | None = None


# --- Version 1.1.1: Konfigurierbare Aufgaben-Spalten ---
class TaskColumnOut(BaseModel):
    id: int
    key: str
    label: str
    sort_order: int
    is_done: bool


class TaskColumnCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    is_done: bool = False


class TaskColumnUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    is_done: bool | None = None


class TaskColumnReorder(BaseModel):
    ordered_ids: list[int]


# --- Version 1.1.2: Checklisten in Aufgaben ---
class TaskChecklistItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class TaskChecklistItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    done: bool | None = None


# --- Version 1.1.3: E-Mail-Benachrichtigung bei Aufgaben-Zuweisung ---
class TaskSettingsOut(BaseModel):
    notify_on_assignment: bool


class TaskSettingsUpdate(BaseModel):
    notify_on_assignment: bool


# --- Version 1.2.15: Positionen je Dachfläche und saisonale Wartungsfenster ---
class MaintenanceContractItemOut(BaseModel):
    id: int
    contract_id: int
    roof_area_id: int
    roof_area_name: str | None = None
    maintenance_window_id: int
    maintenance_window_label: str | None = None
    template_project_id: int | None = None
    template_project_number: str | None = None
    inspection_template_id: int | None = None
    inspection_template_label: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    next_due_date: date
    archived: bool
    is_due: bool
    is_overdue: bool


class MaintenanceContractItemCreate(BaseModel):
    roof_area_id: int
    maintenance_window_id: int
    description: str | None = None
    template_project_id: int | None = None
    inspection_template_id: int | None = None
    duration_minutes: int | None = None


class MaintenanceContractItemUpdate(BaseModel):
    roof_area_id: int
    maintenance_window_id: int
    description: str | None = None
    template_project_id: int | None = None
    inspection_template_id: int | None = None
    duration_minutes: int | None = None


class MaintenanceContractCreateProjectRequest(BaseModel):
    item_id: int | None = None


class MaintenanceWindowOut(BaseModel):
    id: int
    label: str
    month_from: int
    month_to: int
    sort_order: int


class MaintenanceWindowCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    month_from: int
    month_to: int


class MaintenanceWindowUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    month_from: int
    month_to: int


class MaintenanceWindowReorder(BaseModel):
    ordered_ids: list[int]


# --- Version 1.2.0: Wartungsverträge ---
class MaintenanceContractOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str | None = None
    property_id: int | None = None
    property_name: str | None = None
    property_address: str | None = None
    property_postal_code: str | None = None
    property_city: str | None = None
    title: str
    interval_months: int
    next_due_date: date
    template_project_id: int | None = None
    template_project_number: str | None = None
    responsible_employee_id: int | None = None
    responsible_employee_name: str | None = None
    status: str
    archived: bool
    notes: str | None = None
    is_due: bool
    items: list[MaintenanceContractItemOut] = []
    created_at: datetime
    updated_at: datetime


class MaintenanceContractCreate(BaseModel):
    customer_id: int
    property_id: int | None = None
    title: str = Field(min_length=1, max_length=255)
    interval_months: int = 12
    next_due_date: date
    template_project_id: int | None = None
    responsible_employee_id: int | None = None
    notes: str | None = None


class MaintenanceContractUpdate(BaseModel):
    property_id: int | None = None
    title: str = Field(min_length=1, max_length=255)
    interval_months: int
    next_due_date: date
    template_project_id: int | None = None
    responsible_employee_id: int | None = None
    notes: str | None = None


class MaintenanceContractStatusUpdate(BaseModel):
    status: str


# --- Version 1.2.12: Wartungsvertrag aus einem bestehenden Projekt erzeugen ---
class MaintenanceContractFromProjectCreate(BaseModel):
    interval_months: int = 12
    next_due_date: date
    responsible_employee_id: int | None = None


# --- Version 1.2.6: Einstellungen für Wartungen & Reparaturen ---
class MaintenanceSettingsOut(BaseModel):
    reminder_lead_days: int
    use_roof_area_items: bool
    default_responsible_employee_id: int | None = None
    default_responsible_employee_name: str | None = None


class MaintenanceSettingsUpdate(BaseModel):
    reminder_lead_days: int
    use_roof_area_items: bool = False
    default_responsible_employee_id: int | None = None


# --- Version 1.3.0: Monteursansicht (/vor-ort) ---
class MobileSettingsOut(BaseModel):
    shift_end_time: str  # "HH:MM", siehe mobile_settings_to_dict() in app/mobile_settings.py


class MobileSettingsUpdate(BaseModel):
    shift_end_time: str = Field(pattern=r"^\d{2}:\d{2}$")


# --- Version 1.2.12: Schnellauftrag für Reparatur/Wartung ---
class QuickServiceOrderCreate(BaseModel):
    customer_id: int
    property_id: int | None = None
    order_type: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    caseworker_employee_id: int | None = None
    execution_start: date | None = None


class QuickServiceOrderOut(BaseModel):
    project_id: int
    order_id: int
    order_number: str


# --- Version 1.2.16: Strukturierte Prüfpunkte für Einsatzberichte ---
class InspectionTemplateItemOut(BaseModel):
    id: int
    template_id: int
    sort_order: int
    group_name: str | None = None
    component_type: str | None = None
    text: str
    item_type: str
    required: bool
    target_min: Decimal | None = None
    target_max: Decimal | None = None
    unit: str | None = None
    photo_required: bool
    photo_before_after: bool


class InspectionTemplateItemCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    item_type: str
    group_name: str | None = None
    component_type: str | None = None
    required: bool = False
    target_min: Decimal | None = None
    target_max: Decimal | None = None
    unit: str | None = None
    photo_required: bool = False
    photo_before_after: bool = False
    sort_order: int = 100


class InspectionTemplateItemUpdate(InspectionTemplateItemCreate):
    pass


class InspectionTemplateOut(BaseModel):
    id: int
    label: str
    roof_type: str | None = None
    version: int
    description: str | None = None
    sort_order: int
    archived: bool
    item_count: int
    items: list[InspectionTemplateItemOut] = []
    created_at: datetime
    updated_at: datetime


class InspectionTemplateCreate(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    roof_type: str | None = None
    description: str | None = None


class InspectionTemplateUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    roof_type: str | None = None
    description: str | None = None


class RoofTypeTemplateDefaultOut(BaseModel):
    """Zeile der expliziten Dachtyp -> Standardvorlage-Zuordnung (seit 1.2.22)."""
    roof_type: str
    roof_type_label: str
    inspection_template_id: int | None = None
    inspection_template_label: str | None = None


class RoofTypeTemplateDefaultUpdate(BaseModel):
    inspection_template_id: int | None = None


class InspectionTemplateCopy(BaseModel):
    label: str = Field(min_length=1, max_length=160)


class InspectionItemOut(BaseModel):
    id: int
    service_report_id: int
    template_item_id: int | None = None
    roof_component_id: int | None = None
    roof_area_id: int | None = None
    sort_order: int
    group_name: str | None = None
    text: str
    item_type: str
    required: bool
    target_min: Decimal | None = None
    target_max: Decimal | None = None
    unit: str | None = None
    photo_required: bool
    photo_before_after: bool
    result: str | None = None
    condition_grade: int | None = None
    measured_value: Decimal | None = None
    quantity: Decimal | None = None
    duration_minutes: int | None = None
    notes: str | None = None
    recorded_at: datetime | None = None
    recorded_by_employee_id: int | None = None
    client_uuid: str | None = None


class InspectionItemCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    item_type: str
    group_name: str | None = None
    required: bool = False
    target_min: Decimal | None = None
    target_max: Decimal | None = None
    unit: str | None = None
    roof_component_id: int | None = None
    roof_area_id: int | None = None


class InspectionItemResultUpdate(BaseModel):
    result: str | None = None
    condition_grade: int | None = None
    measured_value: Decimal | None = None
    quantity: Decimal | None = None
    duration_minutes: int | None = None
    notes: str | None = None
    client_uuid: str | None = None
    recorded_by_employee_id: int | None = None


class InspectionItemsSyncResult(BaseModel):
    added: int
    items: list[InspectionItemOut]


# --- Version 1.2.1: Digitale Einsatzberichte ---
class ServiceReportRoofAreaOut(BaseModel):
    """Eine an einem ServiceReport beteiligte Dachfläche (seit 1.2.22) -- einheitliche
    Ausgabe für neue Mehrflächen-Berichte UND (aus den Legacy-Spalten synthetisiert) für
    Altbestand-Berichte vor 1.2.22, siehe report_to_dict()."""
    roof_area_id: int
    roof_area_name: str | None = None
    inspection_template_id: int | None = None
    inspection_template_label: str | None = None
    inspection_template_version: int | None = None


class ServiceReportOut(BaseModel):
    id: int
    order_id: int
    order_number: str | None = None
    order_title: str | None = None
    report_type: str
    report_type_label: str
    description: str | None = None
    created_by_employee_id: int | None = None
    created_by_employee_name: str | None = None
    performed_at: date
    signature_name: str | None = None
    signed_at: datetime | None = None
    installer_signature_name: str | None = None
    installer_signed_at: datetime | None = None
    status: str
    maintenance_contract_id: int | None = None
    maintenance_contract_item_id: int | None = None
    advance_due_date_on_sign: bool = False
    # Legacy (vor 1.2.22, ein Bericht = eine Fläche) -- roof_areas ist der einheitliche Lesepfad.
    roof_area_id: int | None = None
    roof_area_name: str | None = None
    inspection_template_id: int | None = None
    inspection_template_label: str | None = None
    inspection_template_version: int | None = None
    roof_areas: list[ServiceReportRoofAreaOut] = []
    created_at: datetime
    updated_at: datetime


class ServiceReportCreate(BaseModel):
    report_type: str
    description: str | None = None
    created_by_employee_id: int | None = None
    performed_at: date | None = None
    roof_area_ids: list[int] | None = None
    inspection_template_id: int | None = None


class ServiceReportUpdate(BaseModel):
    report_type: str
    description: str | None = None
    performed_at: date


class ServiceReportSign(BaseModel):
    """Seit 1.3.0: zwei Unterschriften in einem Aufruf (Monteur zuerst, dann Kunde -- Reihenfolge
    auf dem Gerät, Tablet wird nach der Monteursunterschrift weitergereicht). customer_* sind die
    API-seitig umbenannten, aber unverändert auf ServiceReport.signature_path/-name gemappten
    Felder des Kunden -- siehe sign_report()."""
    installer_signature_png_base64: str = Field(min_length=1)
    installer_signature_name: str = Field(min_length=1, max_length=160)
    customer_signature_png_base64: str = Field(min_length=1)
    customer_signature_name: str = Field(min_length=1, max_length=160)


# --- Version 1.2.17: Mängel und Fotos am Einsatzbericht ---
class FindingOut(BaseModel):
    id: int
    service_report_id: int
    order_id: int | None = None
    order_number: str | None = None
    property_id: int | None = None
    property_name: str | None = None
    customer_name: str | None = None
    inspection_item_id: int | None = None
    roof_component_id: int | None = None
    roof_component_name: str | None = None
    description: str
    severity: str
    severity_label: str
    action: str
    action_label: str
    follow_up_order_id: int | None = None
    follow_up_project_id: int | None = None
    follow_up_task_id: int | None = None
    resubmission_date: date | None = None
    status: str
    status_label: str
    closed_at: datetime | None = None
    closed_by_employee_id: int | None = None
    closed_by_employee_name: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by_employee_id: int | None = None
    client_uuid: str | None = None
    photo_count: int


class FindingCreate(BaseModel):
    description: str = Field(min_length=1)
    severity: str
    action: str
    inspection_item_id: int | None = None
    roof_component_id: int | None = None
    resubmission_date: date | None = None
    created_by_employee_id: int | None = None


class FindingFollowupUpdate(BaseModel):
    status: str | None = None
    action: str | None = None
    resubmission_date: date | None = None
    closed_by_employee_id: int | None = None


class ServiceReportPhotoOut(BaseModel):
    id: int
    service_report_id: int
    inspection_item_id: int | None = None
    finding_id: int | None = None
    kind: str
    original_filename: str | None = None
    caption: str | None = None
    sort_order: int
    created_at: datetime
    created_by_employee_id: int | None = None
    client_uuid: str | None = None


# --- Version 1.2.23: Materialerfassung am Einsatzbericht ---
class ServiceReportMaterialOut(BaseModel):
    id: int
    service_report_id: int
    material_id: int | None = None
    description: str
    quantity: Decimal
    unit: str | None = None
    roof_area_id: int | None = None
    inspection_item_id: int | None = None
    finding_id: int | None = None
    notes: str | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime
    created_by_employee_id: int | None = None
    client_uuid: str | None = None


class ServiceReportMaterialCreate(BaseModel):
    material_id: int | None = None
    description: str | None = None
    quantity: Decimal
    unit: str | None = None
    roof_area_id: int | None = None
    inspection_item_id: int | None = None
    finding_id: int | None = None
    notes: str | None = None
    created_by_employee_id: int | None = None
    client_uuid: str | None = None


class ServiceReportMaterialUpdate(BaseModel):
    material_id: int | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    roof_area_id: int | None = None
    inspection_item_id: int | None = None
    finding_id: int | None = None
    notes: str | None = None
