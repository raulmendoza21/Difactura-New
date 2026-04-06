from app.services.field_extraction.amount_parts.core import extract_iva_percent
from app.services.field_extraction.amount_parts.summary import extract_value_column_tax_summary


def test_extract_iva_percent_prefers_indirect_tax_rate_over_withholding_rate():
    lines = [
        "FACTURA",
        "RETENCION IRPF 15%",
        "IGIC 7%",
        "CUOTA IGIC 1,75",
        "TOTAL 26,75",
    ]

    rate = extract_iva_percent("\n".join(lines), lines)

    assert rate == 7.0


def test_extract_value_column_tax_summary_ignores_withholding_like_percentage_when_tax_rate_is_present():
    lines = [
        "Base imponible",
        "Total",
        "Impuestos % Impuestos",
        "Valor",
        "15%",
        "7%",
        "1,75",
        "25,00",
        "26,75",
    ]
    upper_lines = [line.upper() for line in lines]

    summary = extract_value_column_tax_summary(lines, upper_lines)

    assert summary["iva_porcentaje"] == 7.0
    assert summary["iva"] == 1.75
    assert summary["base_imponible"] == 25.0
    assert summary["total"] == 26.75
