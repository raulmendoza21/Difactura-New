from benchmarks.real_invoices.run_benchmark import (
    _build_synthetic_case_result,
    _build_family_summary,
    _build_field_summary,
    _build_route_overrides,
    _collect_checks,
    _fuzzy_contains_text,
)
from app.models.document_contract import build_normalized_document_from_invoice_data
from app.models.extraction_result import ExtractionResult
from app.models.invoice_model import InvoiceData, LineItem


def test_collect_checks_reads_extraction_result_and_normalized_document():
    invoice = InvoiceData(
        numero_factura="F-2026-001",
        tipo_factura="compra",
        fecha="2026-03-15",
        proveedor="Proveedor Demo SL",
        cif_proveedor="B12345678",
        cliente="Disoft Servicios Informaticos SL",
        cif_cliente="B35222249",
        base_imponible=100.0,
        iva_porcentaje=7.0,
        iva=7.0,
        total=107.0,
        lineas=[LineItem(descripcion="Servicio mensual", cantidad=1, precio_unitario=100, importe=100)],
    )
    normalized = build_normalized_document_from_invoice_data(
        invoice,
        document_type="factura_completa",
        tax_regime="IGIC",
    )
    result = ExtractionResult(
        data=invoice,
        normalized_document=normalized,
    )
    case = {
        "family": "purchase_supplier_single_unit",
        "expected": {
            "numero_factura": "F-2026-001",
            "tipo_factura": "compra",
            "fecha": "2026-03-15",
            "proveedor_contains": "Proveedor Demo",
            "cif_proveedor": "B12345678",
            "cliente_contains": "Disoft",
            "cif_cliente": "B35222249",
            "issuer_contains": "Proveedor Demo",
            "issuer_tax_id": "B12345678",
            "recipient_contains": "Disoft",
            "recipient_tax_id": "B35222249",
            "base_imponible": 100.0,
            "iva_porcentaje": 7.0,
            "iva": 7.0,
            "total": 107.0,
            "normalized_subtotal": 100.0,
            "document_type": "factura_completa",
            "line_count": 1,
            "line_total_sum": 100.0,
            "line_descriptions_contain": ["Servicio mensual"],
        },
    }

    checks = _collect_checks(result, case)

    assert checks
    assert all(check["ok"] for check in checks)
    assert any(check["field"] == "normalized.classification.document_type" for check in checks)
    assert any(check["field"] == "legacy.lineas.sum_importe" for check in checks)


def test_field_and_family_summary_aggregate_ratios():
    checks = [
        {"field": "legacy.numero_factura", "ok": True, "family": "sale"},
        {"field": "legacy.numero_factura", "ok": False, "family": "sale"},
        {"field": "normalized.classification.document_type", "ok": True, "family": "purchase"},
    ]
    outcomes = [
        {"family": "sale", "ok": False, "checks": checks[:2]},
        {"family": "purchase", "ok": True, "checks": checks[2:]},
    ]

    field_summary = _build_field_summary(checks)
    family_summary = _build_family_summary(outcomes)

    numero_factura = next(item for item in field_summary if item["field"] == "legacy.numero_factura")
    sale_family = next(item for item in family_summary if item["family"] == "sale")

    assert numero_factura["passed"] == 1
    assert numero_factura["total"] == 2
    assert sale_family["cases_passed"] == 0
    assert sale_family["cases_total"] == 1
    assert sale_family["checks_passed"] == 1
    assert sale_family["checks_total"] == 2


def test_build_route_overrides_exposes_known_benchmark_routes():
    local_only = _build_route_overrides("local_only")
    mistral_primary = _build_route_overrides("mistral_primary")

    assert local_only["document_parser_force_provider"] == "local"
    assert local_only["document_parser_fallback_enabled"] is False
    assert mistral_primary["document_parser_provider"] == "mistral"
    assert mistral_primary["document_parser_fallback_provider"] == "local"


def test_build_synthetic_case_result_supports_raw_text_cases(tmp_path):
    case = {
        "id": "synthetic_company_to_company_iva",
        "family": "label_value_invoice",
        "raw_text": "\n".join(
            [
                "FACTURA",
                "Numero de factura: FV-2026-001",
                "Fecha: 15/03/2026",
                "Proveedor: Soluciones Delta SL",
                "CIF: B12345678",
                "Cliente: Beta Consultoria SL",
                "CIF: B87654321",
                "Base imponible: 100,00",
                "IVA 21%: 21,00",
                "Total: 121,00",
                "Servicio mensual de mantenimiento 100,00",
            ]
        ),
        "company_context": {
            "name": "Beta Consultoria SL",
            "tax_id": "B87654321",
        },
        "expected": {
            "numero_factura": "FV-2026-001",
            "tipo_factura": "compra",
            "cif_proveedor": "B12345678",
            "cif_cliente": "B87654321",
            "total": 121.0,
        },
    }

    result, summary_meta = _build_synthetic_case_result(case, tmp_path)
    checks = _collect_checks(result, case)

    assert summary_meta["provider"] == "synthetic_text"
    assert result["data"].numero_factura == "FV-2026-001"
    assert result["data"].cif_proveedor == "B12345678"
    assert result["data"].cif_cliente == "B87654321"
    assert any(check["field"] == "legacy.total" and check["ok"] for check in checks)


def test_fuzzy_contains_text_accepts_small_ocr_typos_in_line_descriptions():
    assert _fuzzy_contains_text(
        "ANTIVIRUE AVAST PREMIUM BUSINESS SECURITY 1YEAR 1-4 USUARIOS (KIT DIGITAL)",
        "ANTIVIRUS AVAST",
    )
    assert _fuzzy_contains_text(
        "Mantenimiento del Programa de Facturación Faodis",
        "Mantenimiento del Programa de Facturación Facdis",
    )


def test_fuzzy_contains_text_rejects_meaningfully_truncated_description():
    assert not _fuzzy_contains_text("Continuidad", "Continuidad - Tributos")
