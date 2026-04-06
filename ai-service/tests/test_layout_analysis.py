from app.models.document_bundle import BoundingBox, DocumentSpan
from app.services.layout_analysis.parties import build_party_regions


def _span(span_id: str, text: str, x0: float, y0: float, x1: float, y1: float) -> DocumentSpan:
    return DocumentSpan(
        span_id=span_id,
        page=1,
        text=text,
        bbox=BoundingBox.from_points(x0, y0, x1, y1),
        source="ocr",
        engine="tesseract",
    )


def test_build_party_regions_keeps_party_signals_below_base_header_cutoff():
    spans = [
        _span("s1", "FACTURA", 50, 40, 220, 80),
        _span("s2", "Proveedor Atlantico SL", 40, 120, 340, 155),
        _span("s3", "Cliente Final SL", 430, 120, 700, 155),
        _span("s4", "NIF: B12345678", 40, 520, 250, 555),
        _span("s5", "NIF: B87654321", 430, 520, 650, 555),
        _span("s6", "TOTAL 121,00", 500, 860, 700, 900),
    ]

    regions = build_party_regions(
        page_number=1,
        spans=spans,
        company_context={"name": "Proveedor Atlantico SL", "tax_id": "B12345678"},
    )

    region_map = {region.region_type: region for region in regions}

    assert "header_left" in region_map
    assert "header_right" in region_map
    assert "company_anchor" in region_map
    assert "B12345678" in region_map["header_left"].text
    assert "B87654321" in region_map["header_right"].text
    assert "Proveedor Atlantico SL" in region_map["company_anchor"].text
