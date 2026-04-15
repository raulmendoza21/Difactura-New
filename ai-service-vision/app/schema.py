"""Invoice JSON schema — Spanish/Canary Islands invoices (IVA + IGIC)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    numero: str = ""
    referencia: str = ""
    descripcion: str = ""
    unidad_medida: str = ""
    cantidad: float | None = None
    precio_unitario: float | None = None
    descuento_porcentaje: float | None = None
    descuento_importe: float | None = None
    importe_total: float | None = None


class TaxBreakdown(BaseModel):
    base_imponible: float | None = None
    tipo_porcentaje: float | None = None
    cuota: float | None = None


class InvoiceResult(BaseModel):
    # ── Identificación ─────────────────────────────────────────────────────────
    numero_factura: str = ""
    numero_factura_rectificada: str = ""   # si es factura rectificativa
    serie: str = ""
    tipo_factura: str = ""                 # factura / factura_simplificada / factura_rectificativa / ticket

    # ── Fechas ─────────────────────────────────────────────────────────────────
    fecha_emision: str = ""                # YYYY-MM-DD
    hora_emision: str = ""                 # HH:MM
    fecha_vencimiento: str = ""            # YYYY-MM-DD
    fecha_operacion: str = ""              # YYYY-MM-DD (si difiere de emisión)

    # ── Emisor ─────────────────────────────────────────────────────────────────
    emisor_nombre: str = ""
    emisor_nif: str = ""
    emisor_direccion: str = ""
    emisor_cp: str = ""
    emisor_ciudad: str = ""
    emisor_pais: str = ""

    # ── Receptor ───────────────────────────────────────────────────────────────
    receptor_nombre: str = ""
    receptor_nif: str = ""
    receptor_direccion: str = ""
    receptor_cp: str = ""
    receptor_ciudad: str = ""
    receptor_pais: str = ""

    # ── Condiciones ────────────────────────────────────────────────────────────
    moneda: str = "EUR"
    condiciones_pago: str = ""
    forma_pago: str = ""
    cuenta_bancaria: str = ""

    # ── Importes ───────────────────────────────────────────────────────────────
    base_imponible: float | None = None
    descuento_global: float | None = None

    # IVA / IGIC (pueden coexistir múltiples tramos)
    regimen_fiscal: str = ""               # IVA / IGIC / AIEM / exento
    iva_porcentaje: float | None = None    # tipo principal
    iva_cuota: float | None = None
    desglose_impuestos: list[TaxBreakdown] = Field(default_factory=list)

    # Retención IRPF
    retencion_porcentaje: float | None = None
    retencion_importe: float | None = None

    # Recargo de equivalencia
    recargo_porcentaje: float | None = None
    recargo_importe: float | None = None

    total_factura: float | None = None

    # ── Líneas ─────────────────────────────────────────────────────────────────
    lineas: list[LineItem] = Field(default_factory=list)

    # ── Meta ───────────────────────────────────────────────────────────────────
    observaciones: str = ""


# ── JSON schema string that goes into the prompt ───────────────────────────────
INVOICE_SCHEMA_PROMPT = """\
Analiza la factura y devuelve ÚNICAMENTE un objeto JSON válido con esta estructura exacta.
Para campos no visibles en el documento: null (numéricos) o "" (texto). No inventes datos.

INSTRUCCIÓN CADENA-DE-PENSAMIENTO — el campo "_razonamiento" es OBLIGATORIO y debe \
rellenarse ANTES que cualquier otro campo con exactamente estos cuatro puntos:
  "1.Nº: etiqueta=<etiqueta exacta vista>, valor=<valor>.
   2.Fecha: etiqueta=<etiqueta exacta vista>, valor=<YYYY-MM-DD>.
   3.Impuestos: <N> fila(s) → [base=X tipo=Y% cuota=Z] (una entrada por fila).
   4.Líneas: <N> fila(s). Columnas: [col1, col2, ...]. Verificación: \
línea1 importe=cant×precio ✓/✗, línea2 ... (al menos 3 primeras)."

{
  "_razonamiento": "1.Nº: etiqueta=..., valor=... 2.Fecha: etiqueta=..., valor=... 3.Impuestos: N fila(s) → [base=X tipo=Y% cuota=Z] ... 4.Líneas: N fila(s).",

  "numero_factura": "número de factura exacto tal cual aparece (NO nº pedido ni nº albarán)",
  "numero_factura_rectificada": "",
  "serie": "",
  "tipo_factura": "factura | factura_simplificada | factura_rectificativa | ticket",

  "fecha_emision": "YYYY-MM-DD",
  "hora_emision": "",
  "fecha_vencimiento": "",
  "fecha_operacion": "",

  "emisor_nombre": "nombre o razón social completa del emisor",
  "emisor_nif": "NIF/CIF/NIE del emisor exacto",
  "emisor_direccion": "dirección completa del emisor",
  "emisor_cp": "código postal del emisor",
  "emisor_ciudad": "ciudad del emisor",
  "emisor_pais": "ES",

  "receptor_nombre": "nombre o razón social completa del receptor",
  "receptor_nif": "NIF/CIF/NIE del receptor exacto",
  "receptor_direccion": "dirección completa del receptor",
  "receptor_cp": "código postal del receptor",
  "receptor_ciudad": "ciudad del receptor",
  "receptor_pais": "ES",

  "moneda": "EUR",
  "condiciones_pago": "",
  "forma_pago": "transferencia | tarjeta | efectivo | domiciliación | etc.",
  "cuenta_bancaria": "IBAN completo si aparece",

  "base_imponible": 0.00,
  "descuento_global": null,
  "regimen_fiscal": "IVA | IGIC | exento",
  "iva_porcentaje": null,
  "iva_cuota": 0.00,
  "desglose_impuestos": [
    { "base_imponible": 0.00, "tipo_porcentaje": 7.0, "cuota": 0.00 },
    { "base_imponible": 0.00, "tipo_porcentaje": 3.0, "cuota": 0.00 }
  ],
  "retencion_porcentaje": null,
  "retencion_importe": null,
  "recargo_porcentaje": null,
  "recargo_importe": null,
  "total_factura": 0.00,

  "lineas": [
    {
      "numero": "1",
      "referencia": "",
      "descripcion": "descripción completa del artículo o servicio",
      "unidad_medida": "ud / h / kg / etc.",
      "cantidad": 1.0,
      "precio_unitario": 0.00,
      "descuento_porcentaje": null,
      "descuento_importe": null,
      "importe_total": 0.00
    }
  ],

  "observaciones": ""
}

NOTAS SOBRE LÍNEAS:
- Extrae CADA fila de la tabla de artículos/servicios como una entrada en "lineas".
- Lee cada columna por su posición bajo la cabecera, NO mezcles valores de columnas adyacentes.
- "referencia" = código/referencia del artículo si existe (columna "Ref.", "Código", "Referencia").
- "importe_total" = última columna numérica de la fila ("Importe", "Total", "Subtotal"). \
  NUNCA lo dejes en null si hay un valor visible en esa columna. Es OBLIGATORIO extraerlo.
- Verifica: importe_total ≈ cantidad × precio_unitario (± descuento). Si no cuadra, relee la fila.
- En facturas rectificativas los importes pueden ser negativos → extráelos con signo.
- No incluyas filas de subtotales, descuentos globales ni de impuestos en "lineas".

NOTAS SOBRE DESGLOSE:
- UNA entrada por cada tipo impositivo distinto. Si hay IGIC 3% y IGIC 7% → DOS objetos.
- "base_imponible" (raíz) = suma exacta de TODAS las bases del desglose.
- "iva_cuota" (raíz) = suma exacta de TODAS las cuotas del desglose.
- "iva_porcentaje" = tipo único si solo hay uno; null si hay varios tipos distintos.
"""
