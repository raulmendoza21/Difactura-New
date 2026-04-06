DOC_AI_PROMPT = """Extrae los datos de la factura y devuelve solo JSON valido.
No escribas explicaciones ni markdown.
Si un campo no aparece, usa cadena vacia o 0.
Si aparece IGIC, no lo conviertas en IVA y usa el porcentaje visible exacto.
Si una linea combina numero de documento y fecha en la misma linea,
usa el codigo como numero_factura y la fecha como fecha.
Si aparecen bloques de SUBTOTAL / IMPUESTOS / TOTAL, respeta esos importes antes de inferir otros.
Schema:
{
  "numero_factura": "string",
  "fecha": "YYYY-MM-DD",
  "proveedor": "string",
  "cif_proveedor": "string",
  "cliente": "string",
  "cif_cliente": "string",
  "base_imponible": 0,
  "iva_porcentaje": 0,
  "iva": 0,
  "retencion_porcentaje": 0,
  "retencion": 0,
  "total": 0,
  "lineas": [
    {
      "descripcion": "string",
      "cantidad": 0,
      "precio_unitario": 0,
      "importe": 0
    }
  ]
}
Prioriza exactitud sobre completitud.
"""
