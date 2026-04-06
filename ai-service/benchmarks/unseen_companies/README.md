# Benchmark de empresas no vistas

Este benchmark no sustituye al estable de `real_invoices`.

Sirve para medir generalizacion real con:

- empresa nueva
- layout nuevo
- foto mala
- ticket
- multipagina

Tambien sirve como destino natural del corpus sintetico y de perturbaciones visuales
mientras todavia no hay suficientes facturas reales no vistas.

## Regla

Los casos aqui no deben reutilizar familias ni empresas ya estabilizadas como unica referencia.

La idea no es cubrir "empresas", sino cubrir el espacio de variacion documental:

- modalidad de entrada
- layout de partes
- estructura fiscal
- estructura de lineas
- calidad visual / ruido OCR
- casos borde de semantica

La matriz estructurada de familias vive en:

- `ai-service/benchmarks/unseen_companies/family_matrix.json`

Ese archivo debe ser la referencia operativa para:

- decidir que familia cubre cada caso nuevo
- detectar huecos de cobertura
- anadir nuevas variantes sin hardcodes
- justificar por que una mejora aplica a una familia y no a una empresa concreta

## Matriz de cobertura minima

Antes de dar el motor por robusto, este benchmark deberia cubrir como minimo:

- `modality_pdf_digital`
- `modality_pdf_scanned`
- `modality_photo_mobile`
- `modality_ticket`
- `modality_multipage`
- `layout_header_two_columns`
- `layout_shipping_billing`
- `layout_footer_supplier`
- `layout_label_value`
- `layout_tabular`
- `layout_sparse_visual_summary`
- `party_company_vs_person`
- `party_single_tax_id_visible`
- `party_multiple_tax_ids_visible`
- `party_supplier_only_in_footer`
- `fiscal_igic`
- `fiscal_iva`
- `fiscal_irpf`
- `fiscal_multiple_rates`
- `fiscal_tax_included`
- `fiscal_rectificative`
- `line_single`
- `line_multiline`
- `line_codes_and_serials`
- `line_discount`
- `line_page_break`
- `noise_blur`
- `noise_rotation`
- `noise_low_contrast`
- `noise_crop`
- `noise_jpeg_compression`
- `noise_mojibake`
- `noise_shadow`
- `edge_invoice_number_looks_like_tax_id`
- `edge_same_company_in_shipping_and_billing`
- `edge_supplier_legal_footer_only`

## Corpus recomendado por fases

### Fase A: sintetico textual

Objetivo minimo:

- `18` casos de texto puro
- pensados para estresar interpretacion semantica
- sin depender del OCR visual

Cobertura minima:

- venta simple con emisor en cabecera y cliente persona fisica
- compra `shipping/billing` con proveedor solo en pie legal
- compra con IRPF
- rectificativa negativa
- ticket simplificado
- multipagina con tabla
- proveedor y cliente con nombres parecidos
- numero de factura parecido a CIF/NIF
- varios CIF visibles

### Fase B: perturbaciones visuales

Objetivo minimo:

- `24` casos
- partir de `6` documentos base ya estables
- aplicar `4` perturbaciones por documento

Perturbaciones recomendadas:

- rotacion ligera
- blur moderado
- compresion JPEG agresiva
- bajo contraste o sombra

### Fase C: empresas no vistas reales

Objetivo minimo:

- `12` documentos reales no vistos
- `2` por familia documental importante

Familias minimas:

- venta visual resumen
- venta tabular
- compra `shipping/billing`
- compra con retencion
- ticket / simplificada
- multipagina

## Tests metamorfos recomendados

Ademas del benchmark por archivo, conviene anadir invariantes:

- si se cambia `S.L.` por `SL`, la resolucion de partes no debe cambiar
- si el proveedor pasa de cabecera a pie legal, debe seguir detectandose
- si se degradan acentos o aparece mojibake, la familia documental no debe saltar a otra incoherente
- si el numero de factura se parece a un CIF, no debe promocionarse como tax id de partes
- si el bloque `shipping/billing` coincide con la empresa asociada, debe seguir interpretandose como cliente
- si una imagen empeora un poco, no debe cambiar `compra` o `venta` cuando las partes siguen siendo coherentes

## Como usarlo

Con el stack levantado:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py --cases-path /app/benchmarks/unseen_companies/cases.json
```

Para filtrar por tag:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py --cases-path /app/benchmarks/unseen_companies/cases.json --tag unseen_company
```

## Tags recomendados por caso

Usa tags compuestas para poder filtrar por eje de variacion:

- `unseen_company`
- `synthetic`
- `perturbed`
- `modality_pdf_digital`
- `modality_pdf_scanned`
- `modality_photo_mobile`
- `modality_ticket`
- `modality_multipage`
- `layout_shipping_billing`
- `layout_footer_supplier`
- `layout_tabular`
- `layout_label_value`
- `fiscal_igic`
- `fiscal_iva`
- `fiscal_irpf`
- `fiscal_rectificative`
- `noise_blur`
- `noise_rotation`
- `noise_low_contrast`
- `noise_mojibake`
- `edge_invoice_number_looks_like_tax_id`
- `edge_supplier_legal_footer_only`

## Criterio de aceptacion

Una mejora no se considera valida solo porque arregle un caso nuevo.

Debe cumplirse todo esto:

1. `real_invoices` no empeora.
2. El caso nuevo queda anadido como regresion fija.
3. Si el caso representa una variacion nueva, se etiqueta con la matriz correspondiente.
4. Si el bug nace de OCR degradado o layout raro, se intenta anadir una variante sintetica o perturbada del mismo patron.

## Regla de familias

Cada caso nuevo debe responder explicitamente a estas preguntas:

1. que `family_id` cubre dentro de `family_matrix.json`
2. que ejes de variacion activa
3. que riesgo principal estamos intentando blindar

No se acepta una correccion nueva con justificacion del tipo:

- "factura de la empresa X"
- "plantilla del proveedor Y"
- "caso del cliente Z"

La justificacion siempre debe quedar en terminos generales:

- familia documental
- variante visual
- riesgo semantico
- riesgo fiscal
- riesgo de lineas o tax ids

## Estado actual

El arnes ya esta listo, pero este benchmark no quedara validado de verdad hasta meter:

- documentos reales no vistos en `cases.json`
- y, mientras tanto, un primer lote sintetico / perturbado siguiendo esta matriz

Estado actual del corpus sintetico:

- `22` casos sinteticos ya integrados
- cubren:
  - venta visual resumen
  - venta persona fisica en cabecera
  - venta tabular empresa a persona
  - venta foto con blur y sombra
  - compra `shipping/billing` simple, con mojibake y con proveedor solo en pie legal
  - compra `shipping/billing` en `pdf_photo` con proveedor solo en pie legal y sombra
  - compras `label-value` con uno o varios tax ids visibles
  - compra `label-value` con varios tramos fiscales
  - compra con IRPF de proveedor persona fisica
  - compra tabular con descuento
  - compra con codigos y seriales
  - compra multipagina textual
  - ticket supermercado
  - ticket vertical con pago y cambio
  - ticket restaurante con impuesto incluido
  - rectificativa negativa
- validacion actual:
  - `python benchmarks/real_invoices/run_benchmark.py --cases-path benchmarks/unseen_companies/cases.json --route configured`
  - resultado: `22/22 casos correctos`
- validacion cruzada del motor:
  - `python -m pytest ai-service/tests -q` -> `149 passed`
  - `real_invoices` en Docker -> `6/6 casos`, `138/138 checks`
- matriz estructurada disponible:
  - `family_matrix.json` define las familias canonicas que deben guiar las siguientes ampliaciones del corpus
- desde la ultima iteracion, el motor tambien cubre mejor tickets y simplificadas visuales:
  - evita promocionar lineas de pago como resumen fiscal
  - no inventa cliente en tickets sin etiqueta explicita
  - reconstruye lineas con codigos/seriales sin partir una misma compra en varias lineas falsas
  - valida el porcentaje `IVA/IGIC` cuando el ticket solo trae `base + cuota`
