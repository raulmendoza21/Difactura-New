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
Devuelve ÚNICAMENTE un objeto JSON válido con exactamente esta estructura.
Para campos desconocidos usa null (números) o "" (cadenas). No inventes datos.

{
  "numero_factura": "número de factura",
  "numero_factura_rectificada": "número factura rectificada (solo si es rectificativa)",
  "serie": "serie de la factura si la hay",
  "tipo_factura": "factura | factura_simplificada | factura_rectificativa | ticket",

  "fecha_emision": "YYYY-MM-DD",
  "hora_emision": "HH:MM o vacío",
  "fecha_vencimiento": "YYYY-MM-DD o vacío",
  "fecha_operacion": "YYYY-MM-DD o vacío",

  "emisor_nombre": "nombre o razón social del emisor",
  "emisor_nif": "NIF/CIF/NIE del emisor",
  "emisor_direccion": "dirección completa del emisor",
  "emisor_cp": "código postal del emisor",
  "emisor_ciudad": "ciudad del emisor",
  "emisor_pais": "ES u otro código ISO",

  "receptor_nombre": "nombre o razón social del receptor",
  "receptor_nif": "NIF/CIF/NIE del receptor",
  "receptor_direccion": "dirección completa del receptor",
  "receptor_cp": "código postal del receptor",
  "receptor_ciudad": "ciudad del receptor",
  "receptor_pais": "ES u otro código ISO",

  "moneda": "EUR | USD | GBP | ...",
  "condiciones_pago": "contado / 30 días / etc.",
  "forma_pago": "transferencia / tarjeta / efectivo / domiciliación / etc.",
  "cuenta_bancaria": "IBAN si aparece",

  "base_imponible": 0.00,
  "descuento_global": null,
  "regimen_fiscal": "IVA | IGIC | AIEM | exento",
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
      "referencia": "ref/código artículo",
      "descripcion": "descripción del artículo o servicio",
      "unidad_medida": "ud / h / kg / etc.",
      "cantidad": 1.0,
      "precio_unitario": 0.00,
      "descuento_porcentaje": null,
      "descuento_importe": null,
      "importe_total": 0.00
    }
  ],

  "observaciones": "cualquier nota relevante no encuadrada arriba"
}
"""
