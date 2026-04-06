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
    input_kind: str = ""
    text_source: str = ""
    file_name: str = ""
    mime_type: str = ""
    page_count: int = Field(default=0, ge=0)
    language: str = ""
    ocr_engine: str = ""
    preprocessing_steps: list[str] = Field(default_factory=list)
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
    input_kind: str = "",
    text_source: str = "",
    file_name: str = "",
    mime_type: str = "",
    page_count: int = 0,
    ocr_engine: str = "",
    preprocessing_steps: list[str] | None = None,
    extraction_provider: str = "",
    extraction_method: str = "",
    document_type: DocumentType = "desconocido",
    tax_regime: TaxRegime = "UNKNOWN",
    due_date: str = "",
    payment_method: str = "",
    iban: str = "",
    invoice_side: InvoiceSide | None = None,
    operation_kind: OperationKind | None = None,
    is_rectificative: bool | None = None,
    is_simplified: bool | None = None,
    warnings: list[str] | None = None,
    raw_text_excerpt: str = "",
) -> NormalizedInvoiceDocument:
    withholding_total = round(max(0, invoice.retencion or 0), 2)
    subtotal = invoice.base_imponible
    if subtotal == 0 and invoice.lineas:
        subtotal = round(sum(line.importe for line in invoice.lineas if line.importe), 2)
    if subtotal == 0 and invoice.total != 0:
        subtotal = round(invoice.total + withholding_total - invoice.iva, 2)

    tax_breakdown = _build_tax_breakdown(
        subtotal=subtotal,
        tax_amount=invoice.iva,
        tax_rate=invoice.iva_porcentaje,
        total=invoice.total,
        tax_regime=tax_regime,
    )

    line_items = _build_normalized_line_items(
        invoice=invoice,
        subtotal=subtotal,
        tax_regime=tax_regime,
    )

    return NormalizedInvoiceDocument(
        document_meta=DocumentMeta(
            source_channel=source_channel,
            input_kind=input_kind,
            text_source=text_source,
            file_name=file_name,
            mime_type=mime_type,
            page_count=page_count,
            ocr_engine=ocr_engine,
            preprocessing_steps=preprocessing_steps or [],
            extraction_provider=extraction_provider,
            extraction_method=extraction_method,
            extraction_confidence=invoice.confianza,
            warnings=warnings or [],
            raw_text_excerpt=raw_text_excerpt,
        ),
        classification=DocumentClassification(
            document_type=document_type,
            invoice_side=invoice_side or _infer_invoice_side(invoice),
            operation_kind=operation_kind or _infer_operation_kind(invoice),
            is_rectificative=(
                is_rectificative if is_rectificative is not None else document_type in {"factura_rectificativa", "abono"}
            ),
            is_simplified=(
                is_simplified if is_simplified is not None else document_type in {"factura_simplificada", "ticket"}
            ),
        ),
        identity=InvoiceIdentity(
            invoice_number=invoice.numero_factura,
            issue_date=invoice.fecha,
            due_date=due_date,
            rectified_invoice_number=invoice.rectified_invoice_number,
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
            subtotal=subtotal,
            tax_total=invoice.iva,
            withholding_total=withholding_total,
            total=invoice.total,
            amount_due=invoice.total,
        ),
        tax_breakdown=tax_breakdown,
        withholdings=(
            [
                WithholdingBreakdownItem(
                    withholding_type="IRPF",
                    rate=invoice.retencion_porcentaje,
                    taxable_base=subtotal,
                    amount=withholding_total,
                )
            ]
            if withholding_total > 0
            else []
        ),
        line_items=line_items,
        payment_info=PaymentInfo(
            payment_method=payment_method,
            iban=iban,
        ),
    )


def _build_tax_breakdown(
    *,
    subtotal: float,
    tax_amount: float,
    tax_rate: float,
    total: float,
    tax_regime: TaxRegime,
) -> list[TaxBreakdownItem]:
    if subtotal == 0 and tax_amount == 0 and total == 0:
        return []

    is_exempt = tax_regime == "EXEMPT"
    is_not_subject = tax_regime == "NOT_SUBJECT"
    reverse_charge = tax_regime == "REVERSE_CHARGE"

    effective_base = subtotal
    if effective_base == 0 and total != 0 and (is_exempt or is_not_subject or reverse_charge):
        effective_base = total

    tax_code = ""
    if tax_rate > 0:
        tax_code = "general"
    elif is_exempt:
        tax_code = "exempt"
    elif is_not_subject:
        tax_code = "not_subject"
    elif reverse_charge:
        tax_code = "reverse_charge"

    return [
        TaxBreakdownItem(
            tax_regime=tax_regime,
            tax_code=tax_code,
            rate=tax_rate,
            taxable_base=effective_base,
            tax_amount=tax_amount,
            is_exempt=is_exempt,
            is_not_subject=is_not_subject,
            reverse_charge=reverse_charge,
        )
    ]


def _build_normalized_line_items(
    *,
    invoice: InvoiceData,
    subtotal: float,
    tax_regime: TaxRegime,
) -> list[NormalizedLineItem]:
    if not invoice.lineas:
        return []

    line_sum = round(sum(line.importe for line in invoice.lineas if line.importe), 2)
    can_allocate_tax = (
        invoice.iva != 0
        and invoice.iva_porcentaje >= 0
        and line_sum != 0
        and subtotal != 0
        and abs(line_sum - subtotal) <= max(0.02, abs(subtotal) * 0.03)
    )

    normalized_items: list[NormalizedLineItem] = []
    allocated_tax_total = 0.0
    for index, line in enumerate(invoice.lineas):
        line_base = line.importe or round(line.cantidad * line.precio_unitario, 2)
        line_tax = 0.0
        if can_allocate_tax and line_base != 0:
            if index == len(invoice.lineas) - 1:
                line_tax = round(invoice.iva - allocated_tax_total, 2)
            else:
                line_tax = round(invoice.iva * (line_base / line_sum), 2)
                allocated_tax_total = round(allocated_tax_total + line_tax, 2)

        normalized_items.append(
            NormalizedLineItem(
                line_no=index + 1,
                description=line.descripcion,
                quantity=line.cantidad,
                unit_price=line.precio_unitario,
                line_base=line_base,
                tax_regime=tax_regime if can_allocate_tax else "UNKNOWN",
                tax_code="general" if can_allocate_tax and invoice.iva_porcentaje > 0 else "",
                tax_rate=invoice.iva_porcentaje if can_allocate_tax else 0,
                tax_amount=line_tax,
                line_total=round(line_base + line_tax, 2) if can_allocate_tax else line_base,
                confidence=invoice.confianza,
            )
        )

    return normalized_items
