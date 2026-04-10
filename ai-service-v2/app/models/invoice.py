from pydantic import BaseModel, Field


class LineItem(BaseModel):
    descripcion: str = ""
    cantidad: float = 0
    precio_unitario: float = 0
    importe: float = 0


class Entity(BaseModel):
    """An entity (company/person) found in the document."""
    cif: str = ""
    nombre: str = ""


class InvoiceData(BaseModel):
    numero_factura: str = ""
    rectified_invoice_number: str = ""
    tipo_factura: str = ""
    fecha: str = ""

    # Entities found in the document (deterministic, no role assignment)
    entities: list[Entity] = []

    # Role assignment (filled by AI layer)
    proveedor: str = ""
    cif_proveedor: str = ""
    cliente: str = ""
    cif_cliente: str = ""
    operation_side: str = ""  # compra/venta/unknown (filled by AI)

    base_imponible: float = 0
    iva_porcentaje: float = 0
    iva: float = 0
    retencion_porcentaje: float = 0
    retencion: float = 0
    total: float = 0
    tax_regime: str = ""
    confianza: float = Field(default=0, ge=0, le=1)
    lineas: list[LineItem] = []
