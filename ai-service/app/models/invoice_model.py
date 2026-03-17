from pydantic import BaseModel, Field


class LineItem(BaseModel):
    descripcion: str = ""
    cantidad: float = 0
    precio_unitario: float = 0
    importe: float = 0


class InvoiceData(BaseModel):
    numero_factura: str = ""
    tipo_factura: str = ""
    fecha: str = ""
    proveedor: str = ""
    cif_proveedor: str = ""
    cliente: str = ""
    cif_cliente: str = ""
    base_imponible: float = 0
    iva_porcentaje: float = 0
    iva: float = 0
    total: float = 0
    confianza: float = Field(default=0, ge=0, le=1)
    lineas: list[LineItem] = []
