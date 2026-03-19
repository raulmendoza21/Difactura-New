from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.invoice_model import InvoiceData

SourceChannel = Literal["web", "mobile", "camera", "email", "api"]
DocumentType = Literal[
    "desconocido",
    "factura_completa",
    "factura_simplificada",
    "factura_rectificativa",
    "abono",
    "ticket",
    "proforma",
    "dua",
    "otro",
]
InvoiceSide = Literal["recibida", "emitida", "desconocida"]
OperationKind = Literal[
    "compra",
    "venta",
    "gasto",
    "ingreso",
    "inmovilizado",
    "mercaderia",
    "servicio",
    "anticipo",
    "importacion",
    "intracomunitaria",
    "desconocida",
]
TaxRegime = Literal["IGIC", "IVA", "AIEM", "EXEMPT", "NOT_SUBJECT", "REVERSE_CHARGE", "IRPF", "UNKNOWN"]
WithholdingType = Literal["IRPF", "OTHER", "NONE"]
AccountingScenario = Literal[
    "factura_recibida_gasto_corriente",
    "factura_recibida_mercaderias",
    "factura_recibida_inmovilizado",
    "factura_emitida_ingreso",
    "factura_con_retencion",
    "factura_rectificativa_abono",
    "factura_exenta",
    "factura_no_sujeta",
    "factura_con_inversion_sujeto_pasivo",
    "adquisicion_intracomunitaria",
    "importacion_con_dua",
    "anticipo_cliente",
    "anticipo_proveedor",
    "factura_con_varios_tipos",
    "factura_simplificada",
    "desconocido",
]
AccountingLineSide = Literal["DEBE", "HABER"]
AccountingLineSource = Literal["RULE", "AI", "MANUAL"]
ProposalStatus = Literal["draft", "reviewed", "validated"]
CounterpartyRole = Literal["supplier", "customer", "other"]


class DocumentMeta(BaseModel):
    document_id: str = ""
    advisory_id: int | None = None
    company_id: int | None = None
    source_channel: SourceChannel = "web"
    file_name: str = ""
    mime_type: str = ""
    page_count: int = Field(default=0, ge=0)
    language: str = ""
    ocr_engine: str = ""
    extraction_provider: str = ""
    extraction_method: str = ""
    extraction_confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    raw_text_excerpt: str = ""


class DocumentClassification(BaseModel):
    document_type: DocumentType = "desconocido"
    invoice_side: InvoiceSide = "desconocida"
    operation_kind: OperationKind = "desconocida"
    is_rectificative: bool = False
    is_simplified: bool = False
    duplicate_candidate: bool = False


class PartyData(BaseModel):
    name: str = ""
    legal_name: str = ""
    tax_id: str = ""
    vat_id: str = ""
    country: str = ""
    address: str = ""
    postal_code: str = ""
    city: str = ""
    province: str = ""
    email: str = ""
    phone: str = ""
    iban: str = ""


class InvoiceIdentity(BaseModel):
    series: str = ""
    invoice_number: str = ""
    issue_date: str = ""
    operation_date: str = ""
    due_date: str = ""
    period_start: str = ""
    period_end: str = ""
    rectified_invoice_number: str = ""
    order_reference: str = ""
    delivery_note_reference: str = ""
    contract_reference: str = ""


class MonetaryTotals(BaseModel):
    currency: str = "EUR"
    exchange_rate: float | None = None
    subtotal: float = 0
    discount_total: float = 0
    surcharge_total: float = 0
    tax_total: float = 0
    withholding_total: float = 0
    total: float = 0
    amount_due: float = 0


class TaxBreakdownItem(BaseModel):
    tax_regime: TaxRegime = "UNKNOWN"
    tax_code: str = ""
    rate: float = 0
    taxable_base: float = 0
    tax_amount: float = 0
    deductible_percent: float = Field(default=100, ge=0, le=100)
    is_exempt: bool = False
    is_not_subject: bool = False
    reverse_charge: bool = False
    notes: str = ""


class WithholdingBreakdownItem(BaseModel):
    withholding_type: WithholdingType = "NONE"
    rate: float = 0
    taxable_base: float = 0
    amount: float = 0


class NormalizedLineItem(BaseModel):
    line_no: int = Field(default=0, ge=0)
    description: str = ""
    quantity: float = 0
    unit_price: float = 0
    discount_amount: float = 0
    line_base: float = 0
    tax_regime: TaxRegime = "UNKNOWN"
    tax_code: str = ""
    tax_rate: float = 0
    tax_amount: float = 0
    line_total: float = 0
    category_hint: str = ""
    account_hint: str = ""
    product_code: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class PaymentInstallment(BaseModel):
    due_date: str = ""
    amount: float = 0
    payment_method: str = ""


class PaymentInfo(BaseModel):
    payment_method: str = ""
    payment_terms: str = ""
    installments: list[PaymentInstallment] = Field(default_factory=list)
    iban: str = ""
    direct_debit: bool = False
    paid_at_issue: bool = False


class ImportExportInfo(BaseModel):
    dua_number: str = ""
    customs_date: str = ""
    origin_country: str = ""
    destination_country: str = ""
    intracommunity_operator: bool = False
    aiem_amount: float = 0


class NormalizedInvoiceDocument(BaseModel):
    document_meta: DocumentMeta = Field(default_factory=DocumentMeta)
    classification: DocumentClassification = Field(default_factory=DocumentClassification)
    identity: InvoiceIdentity = Field(default_factory=InvoiceIdentity)
    issuer: PartyData = Field(default_factory=PartyData)
    recipient: PartyData = Field(default_factory=PartyData)
    totals: MonetaryTotals = Field(default_factory=MonetaryTotals)
    tax_breakdown: list[TaxBreakdownItem] = Field(default_factory=list)
    withholdings: list[WithholdingBreakdownItem] = Field(default_factory=list)
    line_items: list[NormalizedLineItem] = Field(default_factory=list)
    payment_info: PaymentInfo = Field(default_factory=PaymentInfo)
    import_export_info: ImportExportInfo = Field(default_factory=ImportExportInfo)

    def primary_tax_regime(self) -> TaxRegime:
        if not self.tax_breakdown:
            return "UNKNOWN"
        return self.tax_breakdown[0].tax_regime


class AccountingCounterparty(BaseModel):
    role: CounterpartyRole = "other"
    party_name: str = ""
    party_tax_id: str = ""
    account_code: str = ""


class AccountingProposalLine(BaseModel):
    line_no: int = Field(default=0, ge=0)
    account_code: str = ""
    account_name: str = ""
    side: AccountingLineSide = "DEBE"
    amount: float = Field(default=0, ge=0)
    description: str = ""
    tax_link: str = ""
    analytic_account: str = ""
    cost_center: str = ""
    project_code: str = ""
    maturity_date: str = ""
    source: AccountingLineSource = "RULE"


class AccountingProposal(BaseModel):
    scenario: AccountingScenario = "desconocido"
    posting_date: str = ""
    document_date: str = ""
    journal_code: str = ""
    concept: str = ""
    tax_regime: TaxRegime = "UNKNOWN"
    counterparty: AccountingCounterparty = Field(default_factory=AccountingCounterparty)
    lines: list[AccountingProposalLine] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    rule_trace: list[str] = Field(default_factory=list)
    status: ProposalStatus = "draft"

    def total_debe(self) -> float:
        return round(sum(line.amount for line in self.lines if line.side == "DEBE"), 2)

    def total_haber(self) -> float:
        return round(sum(line.amount for line in self.lines if line.side == "HABER"), 2)

    def is_balanced(self) -> bool:
        return abs(self.total_debe() - self.total_haber()) <= 0.01


class ValidatedResult(BaseModel):
    normalized_document: NormalizedInvoiceDocument = Field(default_factory=NormalizedInvoiceDocument)
    accounting_proposal: AccountingProposal = Field(default_factory=AccountingProposal)
    reviewer_id: int | None = None
    validated_at: str = ""
    validation_notes: str = ""


def _infer_invoice_side(invoice: InvoiceData) -> InvoiceSide:
    if invoice.tipo_factura == "venta":
        return "emitida"
    if invoice.tipo_factura in {"compra", ""}:
        return "recibida"
    return "desconocida"


def _infer_operation_kind(invoice: InvoiceData) -> OperationKind:
    if invoice.tipo_factura == "venta":
        return "venta"
    if invoice.tipo_factura == "compra":
        return "compra"
    return "desconocida"


def build_normalized_document_from_invoice_data(
    invoice: InvoiceData,
    *,
    source_channel: SourceChannel = "web",
    file_name: str = "",
    mime_type: str = "",
    extraction_provider: str = "",
    extraction_method: str = "",
    document_type: DocumentType = "desconocido",
    tax_regime: TaxRegime = "UNKNOWN",
    warnings: list[str] | None = None,
    raw_text_excerpt: str = "",
) -> NormalizedInvoiceDocument:
    tax_breakdown: list[TaxBreakdownItem] = []
    if invoice.base_imponible or invoice.iva or invoice.iva_porcentaje:
        tax_breakdown = [
            TaxBreakdownItem(
                tax_regime=tax_regime,
                tax_code="general" if invoice.iva_porcentaje else "",
                rate=invoice.iva_porcentaje,
                taxable_base=invoice.base_imponible,
                tax_amount=invoice.iva,
            )
        ]

    line_items = [
        NormalizedLineItem(
            line_no=index + 1,
            description=line.descripcion,
            quantity=line.cantidad,
            unit_price=line.precio_unitario,
            line_base=line.importe,
            line_total=line.importe,
            confidence=invoice.confianza,
        )
        for index, line in enumerate(invoice.lineas)
    ]

    return NormalizedInvoiceDocument(
        document_meta=DocumentMeta(
            source_channel=source_channel,
            file_name=file_name,
            mime_type=mime_type,
            extraction_provider=extraction_provider,
            extraction_method=extraction_method,
            extraction_confidence=invoice.confianza,
            warnings=warnings or [],
            raw_text_excerpt=raw_text_excerpt,
        ),
        classification=DocumentClassification(
            document_type=document_type,
            invoice_side=_infer_invoice_side(invoice),
            operation_kind=_infer_operation_kind(invoice),
        ),
        identity=InvoiceIdentity(
            invoice_number=invoice.numero_factura,
            issue_date=invoice.fecha,
        ),
        issuer=PartyData(
            name=invoice.proveedor,
            legal_name=invoice.proveedor,
            tax_id=invoice.cif_proveedor,
        ),
        recipient=PartyData(
            name=invoice.cliente,
            legal_name=invoice.cliente,
            tax_id=invoice.cif_cliente,
        ),
        totals=MonetaryTotals(
            subtotal=invoice.base_imponible,
            tax_total=invoice.iva,
            total=invoice.total,
            amount_due=invoice.total,
        ),
        tax_breakdown=tax_breakdown,
        line_items=line_items,
    )
