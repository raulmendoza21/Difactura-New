from app.services.providers.mistral_document_parser_provider import MistralDocumentParserProvider


class TestMistralDocumentParserProvider:
    def test_expand_page_text_replaces_table_links_with_plain_text(self):
        provider = MistralDocumentParserProvider()

        expanded = provider._expand_page_text(
            {
                "markdown": "# RECTIFICATIVA\n\n[tbl-0.md](tbl-0.md)\n\n[tbl-1.md](tbl-1.md)",
                "tables": [
                    {
                        "id": "tbl-0.md",
                        "content": "| DOCUMENTO | FECHA |\n| --- | --- |\n| AB202600002 | 07-01-2026 |",
                    },
                    {
                        "id": "tbl-1.md",
                        "content": "| CONCEPTO | VALOR |\n| --- | --- |\n| Mantenimiento del Programa de Facturación Facdis | -25,00 |",
                    },
                ],
            }
        )

        assert "[tbl-0.md](tbl-0.md)" not in expanded
        assert "AB202600002" in expanded
        assert "07-01-2026" in expanded
        assert "Mantenimiento del Programa de Facturación Facdis" in expanded

    def test_normalize_ocr_response_uses_one_based_page_numbers(self):
        provider = MistralDocumentParserProvider()

        result = provider._normalize_ocr_response(
            {
                "model": "mistral-ocr-latest",
                "pages": [
                    {
                        "index": 0,
                        "markdown": "Factura\n[tbl-0.md](tbl-0.md)",
                        "dimensions": {"width": 1000, "height": 1200},
                        "tables": [
                            {
                                "id": "tbl-0.md",
                                "content": "| DOCUMENTO | FECHA |\n| --- | --- |\n| F-2026-001 | 15-03-2026 |",
                            }
                        ],
                    }
                ],
            }
        )

        assert result.pages == 1
        assert result.page_entries[0].page_number == 1
        assert "F-2026-001" in result.page_entries[0].text

    def test_expand_page_text_includes_useful_header_when_markdown_misses_identity(self):
        provider = MistralDocumentParserProvider()

        expanded = provider._expand_page_text(
            {
                "header": "FACTURA\nSANTIAGO JORGE NAVARRO SARMIENTO\nNúmero: 14/2025\n43292128X\nFecha: 21/12/2025",
                "markdown": "Cliente: DISOFT\n[tbl-0.md](tbl-0.md)",
                "tables": [
                    {
                        "id": "tbl-0.md",
                        "content": "| CONCEPTO | IMPORTE |\n| --- | --- |\n| Servicios de consultoría estratégica | 15,000.00 € |",
                    }
                ],
            }
        )

        assert "SANTIAGO JORGE NAVARRO SARMIENTO" in expanded
        assert "14/2025" in expanded
        assert "21/12/2025" in expanded
