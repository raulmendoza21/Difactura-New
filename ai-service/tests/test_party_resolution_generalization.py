from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.text_resolution.document_family import document_family_service
from app.services.text_resolution.family_corrections import family_correction_service
from app.services.text_resolution.normalization import invoice_normalization_service
from app.services.text_resolution.party_resolution import party_resolution_service
from app.services.text_resolution.party_resolution_parts.raw_text import extract_parties_from_raw_text


PHOTO_SALE_RAW_TEXT = "\n".join(
    [
        "Disoft",
        "Servicios informáticos",
        "(1568) CARMELO RODRIGUEZ Y SOLEDAD DEL PINO ASESORES, S.C. PROFESIONAL",
        "VALENCIA, 66 - Bajo",
        "35006 LAS PALMAS DE GRAN CANARIA",
        "LAS PALMAS",
        "NIF: J76022912",
        "DISOFT SERVICIOS INFORMATICOS SL",
        "C/ Federico Viera, 163",
        "35012 Las Palmas de Gran Canaria",
        "Tlf. (928) 470347",
        "Mail: administracion@disoftweb.com",
        "Web: www.disoft.es",
        "FACTURA",
        "DOCUMENTO",
        "FECHA",
        "FI202600043",
        "07-01-2026",
        "CONCEPTO",
        "IMPORTE",
        "BASE",
        "%IGIC",
        "CUOTA",
        "SUBTOTAL",
        "IMPUESTOS",
        "TOTAL",
    ]
)

PHOTO_SALE_RAW_TEXT_SECOND = "\n".join(
    [
        "Disoft",
        "Servicios informáticos",
        "(1736) CRISTOBAL M. DIAZ HERNANDEZ",
        "LOS POBRES, 93 (Urb. Palomeros)",
        "38280 TEGUESTE",
        "TENERIFE",
        "NIF: 43611643D",
        "DISOFT SERVICIOS INFORMATICOS SL",
        "C/ Federico Viera, 163",
        "35012 Las Palmas de Gran Canaria",
        "Tlf. (928) 470347",
        "Mail: administracion@disoftweb.com",
        "Web: www.disoft.es",
        "FACTURA",
        "DOCUMENTO",
        "FECHA",
        "FI202600254",
        "11-03-2026",
        "CONCEPTO",
        "IMPORTE",
        "Continuidad - Tributos",
        "81,00",
        "BASE",
        "%/GIC",
        "CUOTA",
        "81,00",
        "7,00",
        "5,67",
        "SUBTOTAL",
        "81,00",
        "IMPUESTOS",
        "5,67",
        "TOTAL",
        "86,67",
    ]
)

COMPANY_CONTEXT = {
    "name": "Disoft Servicios Informaticos SL",
    "tax_id": "B35222249",
}


def test_extract_parties_from_raw_text_prefers_structured_header_block_over_logo_subtitle():
    parties = extract_parties_from_raw_text(PHOTO_SALE_RAW_TEXT)

    assert parties["proveedor"] == "(1568) CARMELO RODRIGUEZ Y SOLEDAD DEL PINO ASESORES, S.C. PROFESIONAL"
    assert parties["cif_proveedor"] == "J76022912"
    assert parties["cliente"] == "DISOFT SERVICIOS INFORMATICOS SL"


def test_party_candidate_score_does_not_penalize_sc_profesional_name_as_if_it_were_an_address():
    score = party_resolution_service.party_candidate_score(
        "CARMELO RODRIGUEZ Y SOLEDAD DEL PINO ASESORES, S.C. PROFESIONAL",
        "J76022912",
    )

    assert score >= 7


def test_family_corrections_swap_company_sale_roles_using_company_context_not_company_name():
    family, _ = document_family_service.detect(
        raw_text=PHOTO_SALE_RAW_TEXT,
        invoice=InvoiceData(
            proveedor="CARMELO RODRIGUEZ Y SOLEDAD DEL PINO ASESORES, S.C. PROFESIONAL",
            cif_proveedor="J76022912",
            cliente="DISOFT SERVICIOS INFORMATICOS SL",
            cif_cliente="J76022912",
        ),
        bundle=DocumentBundle(raw_text=PHOTO_SALE_RAW_TEXT),
        company_context=COMPANY_CONTEXT,
    )

    normalized = InvoiceData(
        proveedor="CARMELO RODRIGUEZ Y SOLEDAD DEL PINO ASESORES, S.C. PROFESIONAL",
        cif_proveedor="J76022912",
        cliente="DISOFT SERVICIOS INFORMATICOS SL",
        cif_cliente="J76022912",
    )
    fallback = normalized.model_copy(deep=True)

    warnings = family_correction_service.apply_family_corrections(
        normalized,
        fallback,
        raw_text=PHOTO_SALE_RAW_TEXT,
        company_context=COMPANY_CONTEXT,
    )

    assert family == "company_sale"
    assert normalized.proveedor == "Disoft Servicios Informaticos SL"
    assert normalized.cif_proveedor == "B35222249"
    assert normalized.cliente == "(1568) CARMELO RODRIGUEZ Y SOLEDAD DEL PINO ASESORES, S.C. PROFESIONAL"
    assert normalized.cif_cliente == "J76022912"
    assert "familia_company_sale_roles_corregidos" in warnings


def test_normalize_invoice_data_restores_external_counterparty_for_visual_sale_when_fallback_client_is_an_address():
    primary = InvoiceData(
        proveedor="Disoft Servicios Informaticos SL",
        cif_proveedor="43611643D",
        cliente="35012 Las Palmas de Gran Canaria",
        cif_cliente="",
        numero_factura="FI202600254",
        fecha="2026-03-11",
        base_imponible=81.0,
        iva_porcentaje=7.0,
        iva=5.67,
        total=86.67,
    )
    fallback = primary.model_copy(deep=True)

    normalized, warnings = invoice_normalization_service.normalize_invoice_data(
        primary,
        fallback,
        raw_text=PHOTO_SALE_RAW_TEXT_SECOND,
        company_context=COMPANY_CONTEXT,
    )

    assert normalized.proveedor == "Disoft Servicios Informaticos SL"
    assert normalized.cif_proveedor == "B35222249"
    assert normalized.cliente == "(1736) CRISTOBAL M. DIAZ HERNANDEZ"
    assert normalized.cif_cliente == "43611643D"
    assert "familia_company_sale_roles_corregidos" in warnings
