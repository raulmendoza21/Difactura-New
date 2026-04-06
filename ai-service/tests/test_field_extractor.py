"""Tests for field_extractor."""

import pytest
from app.models.document_bundle import DocumentBundle, LayoutRegion
from app.services.field_extractor import FieldExtractor
from app.services.field_extraction.bundle import extract_from_bundle
from app.models.invoice_model import InvoiceData


@pytest.fixture
def extractor():
    return FieldExtractor()


class TestFieldExtractor:

    def test_extract_invoice_number(self, extractor):
        text = "Factura: F-2024/001\nFecha: 15/03/2024"
        data = extractor.extract(text)
        assert "2024" in data.numero_factura or "001" in data.numero_factura

    def test_extract_invoice_number_next_line(self, extractor):
        text = "Numero de factura\nAB-2024-77\nFecha: 15/03/2024"
        data = extractor.extract(text)
        assert data.numero_factura == "AB-2024-77"

    def test_extract_invoice_number_inline_numeric_series(self, extractor):
        text = "FACTURA\nNúmero: 14/2025\nFecha: 21/12/2025"
        data = extractor.extract(text)
        assert data.numero_factura == "14/2025"

    def test_extract_date_numeric(self, extractor):
        text = "Factura: 001\nFecha: 15/03/2024\nTotal: 121,00"
        data = extractor.extract(text)
        assert data.fecha == "2024-03-15"

    def test_extract_date_text(self, extractor):
        text = "Factura del 15 de marzo de 2024"
        data = extractor.extract(text)
        assert data.fecha == "2024-03-15"

    def test_extract_cif(self, extractor):
        text = "Proveedor: Empresa SL\nCIF: B12345678\nCliente: Mi empresa\nNIF: 12345678A"
        data = extractor.extract(text)
        assert data.cif_proveedor == "B12345678"

    def test_extract_amounts(self, extractor):
        text = """
        Factura: 001
        Fecha: 01/01/2024
        Base imponible: 100,00
        IVA 21%
        Cuota IVA: 21,00
        Total factura: 121,00
        """
        data = extractor.extract(text)
        assert data.base_imponible == 100.00
        assert data.iva_porcentaje == 21.0
        assert data.total == 121.00

    def test_extract_iva_amount(self, extractor):
        text = """
        Factura: 003
        Fecha: 01/01/2024
        Base imponible: 100,00
        IVA 21%
        Cuota IVA: 21,00
        Total factura: 121,00
        """
        data = extractor.extract(text)
        assert data.iva == 21.00

    def test_infer_missing_iva(self, extractor):
        text = """
        Factura: 002
        Fecha: 01/01/2024
        Base imponible: 200,00
        IVA 21%
        Total factura: 242,00
        """
        data = extractor.extract(text)
        assert data.base_imponible == 200.00
        assert data.iva == 42.00 or data.total == 242.00

    def test_empty_text(self, extractor):
        data = extractor.extract("")
        assert data.numero_factura == ""
        assert data.total == 0.0
        assert data.confianza == 0.0

    def test_extract_parties_from_emisor_cliente_sections(self, extractor):
        text = """
        EMISOR
        CLIENTE
        ATLANTICO SISTEMAS CANARIAS SL.
        DISOFT SOLUCIONES SL.
        CIF: B12345678
        CIF: B87654321
        """
        data = extractor.extract(text)

        assert data.proveedor == "ATLANTICO SISTEMAS CANARIAS SL."
        assert data.cliente == "DISOFT SOLUCIONES SL."
        assert data.cif_proveedor == "B12345678"
        assert data.cif_cliente == "B87654321"

    def test_extracts_mobile_photo_invoice_summary_and_document_number(self, extractor):
        text = """
        DISOFT SERVICIOS INFORMATICOS SL
        ASESORES, S.C.PROFESIONAL
        NIF: J76022912
        FACTURA
        FECHA
        DOCUMENTO
        FI202600043 07-01-2026
        BASE
        %IGIC
        CUOTA
        SUBTOTAL
        312,85
        312,85
        7.00
        21,90
        IMPUESTOS
        21,90
        TOTAL
        334,75
        Registrado en el Registro de Las Palmas con el CIF B35222249 en el Tomo 678.
        """

        data = extractor.extract(text)

        assert data.numero_factura == "FI202600043"
        assert data.fecha == "2026-01-07"
        assert data.base_imponible == 312.85
        assert data.iva_porcentaje == 7.0
        assert data.iva == 21.90
        assert data.total == 334.75
        assert data.cif_proveedor == "B35222249"
        assert data.cif_cliente == "J76022912"

    def test_extracts_header_counterparty_when_sale_photo_lacks_explicit_labels(self, extractor):
        text = """
        DISOFT SERVICIOS INFORMATICOS SL
        (1736) CRISTOBAL M. DIAZ HERNANDEZ
        C/ Federico Viera, 163
        LOS POBRES, 93 (Urb. Palomeros)
        38280 TEGUESTE
        TENERIFE
        NIF: 43611643D
        FACTURA
        DOCUMENTO
        FECHA
        FI202600254 11-03-2026
        IMPORTE
        CONCEPTO
        81,00
        Continuidad - Tributos
        BASE
        %IGIC
        CUOTA
        SUBTOTAL
        81,00
        81,00
        7.00
        5,67
        TOTAL
        86,67
        Registrado en el Registro de Las Palmas con el CIF B35222249.
        """

        data = extractor.extract(text)

        assert data.proveedor == "DISOFT SERVICIOS INFORMATICOS SL"
        assert data.cif_proveedor == "B35222249"
        assert data.cliente == "CRISTOBAL M. DIAZ HERNANDEZ"
        assert data.cif_cliente == "43611643D"

    def test_moves_single_header_nif_to_counterparty_when_issuer_is_company(self, extractor):
        text = """
        DISOFT SERVICIOS INFORMATICOS SL
        (1736) CRISTOBAL M. DIAZ HERNANDEZ
        C/ Federico Viera, 163
        LOS POBRES, 93 (Urb. Palomeros)
        38280 TEGUESTE
        TENERIFE
        NIF: 43611643D
        FACTURA
        DOCUMENTO
        FECHA
        FI202600254 11-03-2026
        IMPORTE
        CONCEPTO
        81,00
        Continuidad - Tributos
        """

        data = extractor.extract(text)

        assert data.proveedor == "DISOFT SERVICIOS INFORMATICOS SL"
        assert data.cif_proveedor == ""
        assert data.cliente == "CRISTOBAL M. DIAZ HERNANDEZ"
        assert data.cif_cliente == "43611643D"

    def test_extracts_footer_summary_when_ocr_places_amounts_before_total_label(self, extractor):
        text = """
        DISOFT SERVICIOS INFORMATICOS SL
        ASESORES, S.C.PROFESIONAL
        NIF: J76022912
        FACTURA
        DOCUMENTO
        FECHA
        FI202600043 07-01-2026
        IMPORTE
        CONCEPTO
        143,85
        Plataforma Web DicRM. Incluye Hosting y Asistenca
        114,00
        Mantenimiento de la Página Web y del dominio. Incluye Hosting
        54,00
        Otros
        1,00
        Dipresencia
        312,85
        %RET
        CUOTA
        SUBTOTAL
        BASE
        %IGIC
        CUOTA
        BASE
        312,85
        7,00
        21,90
        21,90
        IMPUESTOS
        334,75
        TOTAL
        Registrado en el Registro de Las Palmas con el CIF B35222249.
        """

        data = extractor.extract(text)

        assert data.numero_factura == "FI202600043"
        assert data.fecha == "2026-01-07"
        assert data.base_imponible == 312.85
        assert data.iva_porcentaje == 7.0
        assert data.iva == 21.90
        assert data.total == 334.75

    def test_extracts_vertical_amount_description_line_items_from_photo_ocr(self, extractor):
        text = """
        DISOFT SERVICIOS INFORMATICOS SL
        ASESORES, S.C.PROFESIONAL
        FACTURA
        IMPORTE
        CONCEPTO
        143,85
        Plataforma Web DicRM. Incluye Hosting y Asistenca
        114,00
        Mantenimiento de la Página Web y del dominio. Incluye Hosting
        54,00
        Otros
        1,00
        Dipresencia
        312,85
        %RET
        CUOTA
        SUBTOTAL
        BASE
        """

        data = extractor.extract(text)

        assert len(data.lineas) == 4
        assert data.lineas[0].descripcion == "Plataforma Web DicRM. Incluye Hosting y Asistenca"
        assert data.lineas[0].importe == 143.85
        assert data.lineas[1].descripcion == "Mantenimiento de la Página Web y del dominio. Incluye Hosting"
        assert data.lineas[1].importe == 114.00
        assert data.lineas[2].descripcion == "Otros"
        assert data.lineas[2].importe == 54.00
        assert data.lineas[3].descripcion == "Dipresencia"
        assert data.lineas[3].importe == 1.00

    def test_extracts_description_then_amount_single_line_items_from_mistral_text(self, extractor):
        text = """
        FACTURA
        SANTIAGO JORGE NAVARRO SARMIENTO
        Número: 14/2025
        Fecha: 21/12/2025
        Cliente: DISOFT SERVICIOS INFORMÁTICOS, S.L
        Concepto
        Importe
        Servicios de consultoría estratégica y definición funcional para el desarrollo de plataforma tecnológica.
        15,000.00 €
        Total
        15,000.00 €
        IGIC
        7.00% 1,050.00 €
        Rentención I.R.P.F.
        15.00% -2,250.00 €
        Total Factura
        13,800.00 €
        """

        data = extractor.extract(text)

        assert data.numero_factura == "14/2025"
        assert len(data.lineas) == 1
        assert "Servicios de consultoría estratégica" in data.lineas[0].descripcion
        assert data.lineas[0].importe == 15000.0

    def test_extracts_purchase_invoice_from_shipping_billing_and_registry_footer(self, extractor):
        text = """
        €
        Fecha:
        Nº Factura:
        Importe:
        GC 26001163
        26.75
        06/03/2026
        Factura
        Datos de FACTURACIÓN
        Datos de ENVio
        DISOFT SERV. INFORM S.L.
        DISOFT SERVICIOS INFORMATICOS
        CL/FEDERICO VIERA,163
        35012 - LAS PALMAS DE GRAN CANARIA
        Condiciones de pago PRE-PAGO TRANSFERENCIA
        Vencimientos
        06/03/2026
        CIF
        B-35.222.249
        Factura núm
        GC 26001163
        UDS.
        PRECIO % DTO.
        NETO
        Part. Nº
        DESCRIPCIÓN
        De Albarán Nº GC-26004379 del 25/02/2026:
        1,00
        25,00
        25,00
        ESDPBUIY-1A4
        ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY IYEAR 1-4 USUARIOS (KIT DIGITAL)
        WHQD3M9MKK2P6CXWV34MFTR2X
        Observaciones:
        Base imponible
        Total
        Conceptos
        Portes
        Impuestos % Impuestos
        Importe neto
        25,00
        0,00
        26,75
        Valor
        O
        7%
        1,75
        25,00
        Alberto Villacorta, S.L.U. - Registro Mercantil de Las Palmas - CIF B35246388
        """

        data = extractor.extract(text)

        assert data.numero_factura == "GC 26001163"
        assert data.fecha == "2026-03-06"
        assert data.proveedor == "Alberto Villacorta, S.L.U."
        assert data.cif_proveedor == "B35246388"
        assert data.cliente == "DISOFT SERV. INFORM S.L."
        assert data.cif_cliente == "B35222249"
        assert data.base_imponible == 25.00
        assert data.iva_porcentaje == 7.0
        assert data.iva == 1.75
        assert data.total == 26.75
        assert len(data.lineas) == 1
        assert data.lineas[0].descripcion == "ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY IYEAR 1-4 USUARIOS (KIT DIGITAL)"
        assert data.lineas[0].cantidad == 1.0
        assert data.lineas[0].precio_unitario == 25.00
        assert data.lineas[0].importe == 25.00

    def test_extracts_vertical_triplet_line_when_order_is_amount_quantity_unit(self, extractor):
        text = """
        FACTURA
        DESCRIPCIÓN
        Part. Nº
        De Albarán Nº GC-26000253 del 05/01/2026:
        150,00
        6,00
        25,00
        ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY IYEAR 1-4 USUARIOS (KIT DIGITAL)
        ESDPBUIY-1A4
        WD6FYR46M9CVFV9X9CD7G3B7F
        Observaciones:
        Base imponible
        150,00
        """

        data = extractor.extract(text)

        assert len(data.lineas) == 1
        assert data.lineas[0].descripcion == "ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY IYEAR 1-4 USUARIOS (KIT DIGITAL)"
        assert data.lineas[0].cantidad == 6.0
        assert data.lineas[0].precio_unitario == 25.00
        assert data.lineas[0].importe == 150.00

    def test_extracts_multiunit_shipping_billing_purchase_with_footer_supplier(self, extractor):
        text = """
        Fecha:
        09/01/2026
        NÂº Factura:
        GC 26000116
        Importe:
        160,50
        Factura
        Datos de ENVIO
        DISOFT SERVICIOS INFORMATICOS
        CL/FEDERICO VIERA,163
        928470347 -
        35012 LAS PALMAS
        Datos de FACTURACION
        DISOFT SERV. INFORM S.L.
        CL/FEDERICO VIERA,163
        928470347 -
        35012 - LAS PALMAS DE GRAN CANARIA
        CÃ³d. de Cliente:
        180
        CIF
        B-35.222.249
        Factura nÃºm
        GC 26000116
        Entrada factura
        TOMAS M.
        Part. NÂº
        DESCRIPCIÃ“N
        UDS.
        PRECIO % DTO.
        NETO
        ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY 1YEAR 1-4 USUARIOS (KIT DIGITAL)
        6,00
        25,00
        150,00
        Conceptos
        Portes
        Impuestos % Impuestos
        Importe neto
        Descuento
        Ajuste
        Base imponible
        Total
        Valor
        0
        7%
        10,50
        150,00
        0,00
        150,00
        160,50
        Alberto Villacorta, S.L.U. - Registro Mercantil de Las Palmas - CIF B35246388
        """

        data = extractor.extract(text)

        assert data.numero_factura == "GC 26000116"
        assert data.proveedor == "Alberto Villacorta, S.L.U."
        assert data.cif_proveedor == "B35246388"
        assert data.cliente == "DISOFT SERV. INFORM S.L."
        assert data.cif_cliente == "B35222249"

    def test_extracts_multiunit_shipping_billing_purchase_with_header_noise_and_serial_keys(self, extractor):
        text = """
        Factura
        Página 1 de 1
        Ficha: 09/01/2026
        N° Factura: GC 26000116
        E Importe: 160,50
        Datos de ENVÍO
        Datos de FACTURACIÓN
        DISOFT SERVICIOS INFORMATICOS
        DISOFT SERV. INFORM S.L.
        CL/FEDERICO VIERA,163
        CL/FEDERICO VIERA,163
        CIF B-35.222.249
        Factura núm GC 26000116
        Part. N° DESCRIPCIÓN
        UDS. PRECIO % DTO. NETO
        De Albarán N° GC-26000253 del 05/01/2026
        ESDPBUTF-1A4
        ANTIVIRUE AVAST PREMIUM BUSINESS SECURITY 1YEAR 1-4 USUARIOS (KIT DIGITAL)
        6,00
        25,00
        150,00
        WDBFYR46M9CVFV9X9C07G3B7F
        WG247HKCC93JBDQKJG43BDQ7M
        WG49PWG654YQ3GBKBTXJHWMRD
        WGFGDBQTPDCJTWVV74BXY7PWY
        WJB9CDF2PDQQPBXQ8VWWMOT72
        WM66KD2CM2HMXG8VQB7FBBQYK
        Conceptos
        Portes
        Impuestos % Impuestos
        Importe neto
        Descuento
        Ajuste
        Base imponible
        Total
        Valor
        0
        7%
        10,50
        150,00
        0,00
        150,00
        160,50
        Alberto Villacorta, S.L.U. - Registro Mercantil de Las Palmas - CIF B35246388
        """

        data = extractor.extract(text)

        assert data.numero_factura == "GC 26000116"
        assert data.proveedor == "Alberto Villacorta, S.L.U."
        assert data.cif_proveedor == "B35246388"
        assert data.base_imponible == 150.00
        assert data.iva_porcentaje == 7.0
        assert data.iva == 10.50
        assert data.total == 160.50
        assert len(data.lineas) == 1
        assert data.lineas[0].descripcion.startswith("ANTIVIRUE AVAST")
        assert data.lineas[0].cantidad == 6.0
        assert data.lineas[0].precio_unitario == 25.00
        assert data.lineas[0].importe == 150.00

    def test_extracts_invoice_number_and_irpf_withholding(self, extractor):
        text = """
        FACTURA
        Número:
        14/2025
        Fecha:
        21/12/2025
        Total
        15,000.00 €
        IGIC
        7.00%
        1,050.00 €
        Retención I.R.P.F.
        15.00%
        -2,250.00 €
        Total Factura
        13,800.00 €
        """

        data = extractor.extract(text)

        assert data.numero_factura == "14/2025"
        assert data.fecha == "2025-12-21"
        assert data.retencion_porcentaje == 15.0
        assert data.retencion == 2250.0

    def test_assigns_single_visible_client_tax_id_without_promoting_it_to_provider(self, extractor):
        text = """
        FACTURA
        Numero: FC-2026-077
        Fecha: 10/03/2026
        Proveedor: Talleres Rivera SL
        Cliente: Beta Tech Advisors SL
        CIF cliente: B99887766
        Base imponible: 80,00
        IVA 21%: 16,80
        Total: 96,80
        """

        data = extractor.extract(text)

        assert data.proveedor == "Talleres Rivera SL"
        assert data.cliente == "Beta Tech Advisors SL"
        assert data.cif_cliente == "B99887766"

    def test_ignores_contact_and_representative_ids_when_role_tax_ids_are_explicit(self, extractor):
        text = """
        FACTURA
        Numero: PR-2026-044
        Fecha: 20/03/2026
        Proveedor: Suministros Ofimaticos Norte SL
        CIF proveedor: B33445566
        Representante fiscal: Ana Perez DNI 43888777H
        Cliente: Beta Tech Advisors SL
        CIF cliente: B99887766
        Contacto cliente: Laura Medina 44777888L
        Base imponible: 250,00
        IVA 21%: 52,50
        Total factura: 302,50
        """

        data = extractor.extract(text)

        assert data.cif_proveedor == "B33445566"
        assert data.cif_cliente == "B99887766"

    def test_table_header_detection_does_not_start_on_names_that_only_contain_art_substring(self, extractor):
        text = """
        FACTURA
        Numero: FV-2026-088
        Fecha: 24/03/2026
        Emisor:
        Nova Soluciones Tecnicas SL
        CIF: B11223344
        Cliente:
        Marta Suarez Diaz
        NIF: 78543210K
        ARTICULO UDS PRECIO IMPORTE
        Configuracion router 1 60,00 60,00
        Base imponible: 60,00
        IGIC 7%: 4,20
        Total factura: 64,20
        """

        data = extractor.extract(text)

        assert len(data.lineas) == 1
        assert data.lineas[0].descripcion == "Configuracion router"
        assert data.lineas[0].importe == 60.00

    def test_ignores_tax_id_metadata_lines_when_extracting_irpf_amounts(self, extractor):
        text = """
        FACTURA
        Numero: 18/2026
        Fecha: 27/03/2026
        Proveedor: Juan Martin Perez
        NIF proveedor: 43888777H
        Cliente: Beta Tech Advisors SL
        CIF cliente: B99887766
        Base imponible: 1000,00
        IRPF 15%: -150,00
        IVA 21%: 210,00
        Total factura: 1060,00
        """

        data = extractor.extract(text)

        assert data.base_imponible == 1000.00
        assert data.iva == 210.00
        assert data.retencion == 150.00
        assert data.total == 1060.00

    def test_extracts_negative_rectificative_amounts_without_losing_sign(self, extractor):
        text = """
        FACTURA RECTIFICATIVA
        Numero: AB202600002
        Fecha: 07/01/2026
        Base imponible: -25,00
        IGIC 7,00%
        Cuota IGIC: -1,75
        Total factura: -26,75
        """

        data = extractor.extract(text)

        assert data.numero_factura == "AB202600002"
        assert data.fecha == "2026-01-07"
        assert data.base_imponible == -25.00
        assert data.iva_porcentaje == 7.0
        assert data.iva == -1.75
        assert data.total == -26.75

    def test_extracts_supermarket_simplified_ticket(self, extractor):
        text = """
        HiperDino
        DINOSOL SUPERMERCADOS, S.L.
        C.I.F.: B61742565
        9002-SD SCHAMANN
        Telefono: 928256848
        Centro Vend. Documento Fecha Hora
        9002 772330 2026/900213-00004245 19/03/2026 10:12
        ARTICULO IMPORTE
        HIPERDINO CAFE SOLUBLE DESCAFEIN B 2 4,80
        TIRMA CAFE MEZCLA SUAVE 250GRS 3,70
        Total Articulos: 2
        TOTAL COMPRA: 8,50
        TOTAL ENTREGADO: 50,00
        A DEVOLVER: 41,50
        Detalle de pagos
        EFECTIVO 8,50
        Comerciante minorista - FACTURA SIMPLIFICADA
        DOCUMENTO DE VENTA
        """

        data = extractor.extract(text)

        assert data.numero_factura == "2026/900213-00004245"
        assert data.fecha == "2026-03-19"
        assert data.proveedor == "DINOSOL SUPERMERCADOS, S.L."
        assert data.cif_proveedor == "B61742565"
        assert data.cliente == ""
        assert data.total == 8.50
        assert len(data.lineas) == 2
        assert data.lineas[0].descripcion.startswith("HIPERDINO CAFE SOLUBLE")
        assert data.lineas[1].importe == 3.70

    def test_extracts_restaurant_simplified_ticket_with_igic_included(self, extractor):
        text = """
        RESTAURANTE TERRAZA SPLIT'S
        HOSTELERIA GRESSARA, S.L.
        CIF : B35590736
        C.C. LAS ARENAS Tfno: 928 221 471
        FRA. SIMPLIFICADA
        T001-1235663 FECHA 09/01/2025 MESA 102
        UDS DESCRIPCION SALA 1 PVP IMPORTE
        1 PEQUENA AGUA SIN G 1,20 1,20
        1 RACION CROQUETAS D 7,50 7,50
        1 1/2 RACION PESCADO 8,00 8,00
        1 ENVASES PARA LLEVA 0,40 0,40
        TOTAL 17,10
        ENTREGADO 17,10
        CAMBIO 0,00
        FORMA DE PAGO VISA CAJA 17,10
        I.G.I.C. INCLUIDO
        BASE 15,98 CUOTA 1,12
        """

        data = extractor.extract(text)

        assert data.numero_factura == "T001-1235663"
        assert data.fecha == "2025-01-09"
        assert data.proveedor == "HOSTELERIA GRESSARA, S.L."
        assert data.cif_proveedor == "B35590736"
        assert data.total == 17.10
        assert data.base_imponible == 15.98
        assert data.iva == 1.12
        assert len(data.lineas) >= 3

    def test_extracts_supermarket_ticket_ocr_without_using_payment_lines_as_fiscal_totals(self, extractor):
        text = """
        # HiperDino
        DINOSOL SUPERMERCADOS, S.L.
        C.I.F.: B61742565
        9002-SD SCHAMANN
        Teléfono: 928256848
        Centro
        Vend.
        Documento
        Fecha
        Hora
        9002
        772330
        2026/900213-00004245
        19/03/2026
        10:12
        ARTICULO
        IMPORTE
        HIPERDINO CAFE SOLUBLE DESCAFEIN B 2
        4,80
        TIRMA CAFE MEZCLA SUAVE 250GRS
        3,70
        Total Artículos: 2
        TOTAL COMPRA:
        8,50
        TOTAL ENTREGADO:
        50,00
        A DEVOLVER:
        41,50
        Detalle de pagos
        EFFECTIVO
        8,50
        Comerciante minorista - FACTURA SIMPLIFICADA
        ## DOCUMENTO DE VENTA
        """

        data = extractor.extract(text)

        assert data.numero_factura == "2026/900213-00004245"
        assert data.proveedor == "DINOSOL SUPERMERCADOS, S.L."
        assert data.cif_proveedor == "B61742565"
        assert data.cliente == ""
        assert data.cif_cliente == ""
        assert data.total == 8.50
        assert data.iva == 0.0
        assert data.iva_porcentaje == 0.0
        assert len(data.lineas) == 2

    def test_extracts_restaurant_ticket_photo_ocr_without_inventing_customer(self, extractor):
        text = """
        # RESTAURANTE TERRAZA SPLIT'S
        HOSTELERIA GRESSARA, S.L.
        CIF: B-35590736
        C.C. LAS ARENAS-1fno:328 221 471
        FRA. SIMPLIFICADA
        TO01-1235663 FECHA09/01/2025
        CAMARERO-NATALIA MESA 102
        UDS
        DESCRIPCION SALA 1
        PVP
        IMPORTE
        1
        PEQUEÑA AGUA SIN G
        1,20
        1,20
        1
        RACION CROQUETAS D
        7,50
        7,50
        1
        1/2 RACION PESCADO
        8,00
        8,00
        1
        ENVASES PARA LLEVA
        0,40
        0,40
        TOTAL 17,10
        ENTREGADO 17,10
        CAMBIO 0,00
        FORMA DE PAGO VISA CAJA 17,10
        I.G.I.C. INCLUIDO
        BASE 15,98 CUOTA 1,12
        """

        data = extractor.extract(text)

        assert data.numero_factura == "TO01-1235663"
        assert data.proveedor == "HOSTELERIA GRESSARA, S.L."
        assert data.cif_proveedor == "B35590736"
        assert data.cliente == ""
        assert data.cif_cliente == ""
        assert data.base_imponible == 15.98
        assert data.iva_porcentaje == 7.01
        assert data.iva == 1.12
        assert data.total == 17.10
        assert len(data.lineas) == 4
        assert data.lineas[0].descripcion == "PEQUEÑA AGUA SIN G"
        assert data.lineas[1].precio_unitario == 7.50

    def test_extracts_long_ticket_ocr_items_and_does_not_invent_number_when_missing(self, extractor):
        text = """
        Asadero - Grill
        Las Brasas
        MELPER 2001 S.L.
        B35670P98
        Consulta Borrador
        FECHA:26/12/2025 15:25:00
        MESA 43
        Ud. Descripción Precio Importe
        *** NO VALIDO COMO FACTURA ***
        [22WJ-25122601010118-163555]
        6 PAN
        2,00
        12,00
        4 MANTEQUILLA
        2,70
        10,80
        5 CHORIZO UNIDAD
        3,55
        17,75
        IGIC%
        Base
        IGIC
        Total
        7%
        294,29
        20,60
        314,89
        TOTAL 314,89
        """

        data = extractor.extract(text)

        assert data.numero_factura == ""
        assert data.proveedor == "MELPER 2001 S.L."
        assert data.cliente == ""
        assert data.base_imponible == 294.29
        assert data.iva_porcentaje == 7.0
        assert data.iva == 20.60
        assert data.total == 314.89
        assert len(data.lineas) >= 3
        assert data.lineas[0].cantidad == 6.0
        assert data.lineas[0].precio_unitario == 2.00
        assert data.lineas[0].importe == 12.00

    def test_extract_from_bundle_merges_header_parties_and_totals(self, extractor):
        bundle = DocumentBundle(
            raw_text="Factura GC 26001163\nFecha 06/03/2026\nBase imponible 25,00\nTotal 26,75",
            regions=[
                LayoutRegion(
                    region_id="p1:header",
                    region_type="header",
                    page=1,
                    text="Factura\nGC 26001163\nFecha 06/03/2026",
                ),
                LayoutRegion(
                    region_id="p1:parties",
                    region_type="parties",
                    page=1,
                    text="Proveedor: Alberto Villacorta, S.L.U.\nCIF: B35246388\nCliente: DISOFT SERV. INFORM S.L.\nCIF: B35222249",
                ),
                LayoutRegion(
                    region_id="p1:totals",
                    region_type="totals",
                    page=1,
                    text="Base imponible 25,00\nImpuestos 1,75\nTotal 26,75",
                ),
            ],
        )

        data, region_candidates = extractor.extract_from_bundle(bundle)

        assert data.numero_factura == "GC 26001163"
        assert data.fecha == "2026-03-06"
        assert data.proveedor == "Alberto Villacorta, S.L.U."
        assert data.cif_proveedor == "B35246388"
        assert data.cliente == "DISOFT SERV. INFORM S.L."
        assert data.cif_cliente == "B35222249"
        assert data.base_imponible == 25.0
        assert data.total == 26.75
        assert "header" in region_candidates
        assert "parties" in region_candidates
        assert "totals" in region_candidates

    def test_extract_from_bundle_prefers_high_confidence_totals_region_over_full_text_fallback(self, extractor):
        bundle = DocumentBundle(
            raw_text="Base imponible 25,00\nTotal 999,99",
            regions=[
                LayoutRegion(
                    region_id="totals-1",
                    region_type="totals",
                    page=1,
                    confidence=0.92,
                    text="Base imponible 25,00\nTotal 26,75",
                ),
            ],
        )

        def fake_extract_region(text: str) -> InvoiceData:
            if "26,75" in text:
                return InvoiceData(base_imponible=25.0, total=26.75)
            return InvoiceData(base_imponible=25.0, total=999.99)

        merged, region_candidates = extract_from_bundle(bundle, fake_extract_region)

        assert merged.total == 26.75
        assert region_candidates["totals"].total == 26.75
        assert region_candidates["full"].total == 999.99

    def test_extract_from_bundle_keeps_party_name_and_tax_id_from_same_entity(self, extractor):
        bundle = DocumentBundle(
            raw_text="Factura FAC-1",
            regions=[
                LayoutRegion(
                    region_id="header-1",
                    region_type="header",
                    page=1,
                    confidence=0.9,
                    text="Factura FAC-1",
                ),
                LayoutRegion(
                    region_id="parties-1",
                    region_type="parties",
                    page=1,
                    confidence=0.95,
                    text="Proveedor: Alfa Servicios SL\nCIF: B12345678\nCliente: Beta Asesores SCP\nCIF: J76543210",
                ),
                LayoutRegion(
                    region_id="full-1",
                    region_type="full",
                    page=1,
                    confidence=0.6,
                    text="Proveedor: Alfa Servicios SL\nCIF: J76543210\nCliente: Beta Asesores SCP\nCIF: B12345678",
                ),
            ],
        )

        def fake_extract_region(text: str) -> InvoiceData:
            if "Alfa Servicios SL" in text and "B12345678" in text:
                return InvoiceData(
                    proveedor="Alfa Servicios SL",
                    cif_proveedor="B12345678",
                    cliente="Beta Asesores SCP",
                    cif_cliente="J76543210",
                )
            if "Alfa Servicios SL" in text and "J76543210" in text:
                return InvoiceData(
                    proveedor="Alfa Servicios SL",
                    cif_proveedor="J76543210",
                    cliente="Beta Asesores SCP",
                    cif_cliente="B12345678",
                )
            return InvoiceData()

        merged, _region_candidates = extract_from_bundle(bundle, fake_extract_region)

        assert merged.proveedor == "Alfa Servicios SL"
        assert merged.cif_proveedor == "B12345678"
        assert merged.cliente == "Beta Asesores SCP"
        assert merged.cif_cliente == "J76543210"
