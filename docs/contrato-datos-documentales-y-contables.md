# Difactura - Contrato estable del motor documental

## 1. Objetivo

Este documento fija el contrato estable que debe protegerse en la fase actual.

La prioridad ahora no es cerrar:

- la contabilidad final
- la persistencia definitiva por empresa
- la integracion ERP

La prioridad ahora si es cerrar:

- la entrada estable del motor
- la salida estable del motor
- la semantica de evidencia, inferencia y revision
- la compatibilidad temporal con el MVP actual

Documento rector:

- ver `docs/motor-documental-desacoplado.md`

---

## 2. Regla base del contrato

El motor documental debe considerarse una pieza desacoplada.

Por tanto:

- el proveedor OCR no forma parte del contrato estable
- la persistencia del MVP no forma parte del contrato estable
- la BD real futura de la empresa no forma parte del contrato estable

El contrato estable del motor es:

- `engine_request`
- `normalized_document`
- `field_confidence`
- `coverage`
- `evidence`
- `decision_flags`
- `company_match`
- `processing_trace`
- `warnings`
- `raw_text`

Compatibilidad temporal:

- se mantiene una salida `legacy_flattened_v1` para no romper backend ni MVP mientras dura la migracion

---

## 3. Version activa del contrato

- `contract.name`: `difactura.document_engine`
- `contract.version`: `2026-03-30`
- `contract.primary_payload`: `normalized_document`
- `contract.compatibility_mode`: `legacy_flattened_v1`

La salida principal que debe sobrevivir al tiempo es `normalized_document`.
La compatibilidad legacy existe solo para convivir con el MVP actual.

---

## 4. Entrada estable del motor

## 4.1 Forma actual de invocacion

Mientras el motor se consuma por HTTP interno, la invocacion actual puede seguir siendo multipart:

- `file`
- `mime_type`
- `company_name`
- `company_tax_id`

## 4.2 Representacion estable interna

Aunque el transporte actual sea multipart, internamente la entrada estable debe modelarse como:

### `engine_request`

- `file_name`
- `mime_type`
- `company_context`
- `options`

### `engine_request.company_context`

- `name`
- `tax_id`

### `engine_request.options`

- `include_raw_text`
- `include_evidence`
- `include_processing_trace`

Regla:

- `company_context` se usa como pista de desambiguacion, nunca como hardcode de empresa

---

## 4.3 Bundle interno estable

El motor debe convertir cualquier entrada a un `bundle interno` comun antes de resolver campos.

Version interna activa del bundle:

- `bundle.contract.name`: `difactura.document_bundle`
- `bundle.contract.version`: `2026-03-30`

El bundle no es contrato publico de negocio, pero si es contrato interno estable del motor.

Debe incluir, como minimo:

- `contract`
- `input_profile`
- `source_stats`
- `raw_text`
- `page_count`
- `page_texts`
- `pages`
- `spans`
- `regions`
- `candidate_groups`

### `bundle.input_profile`

Debe reflejar:

- `input_kind`
- `text_source`
- `requested_provider`
- `document_provider`
- `fallback_provider`
- `fallback_applied`
- `fallback_reason`
- `is_digital_pdf`
- `used_ocr`
- `used_page_images`
- `ocr_engine`
- `preprocessing_steps`
- `document_family_hint`
- `low_resolution`
- `rotation_hint`
- `input_route`

### `bundle.source_stats`

Debe poder resumir:

- `page_count`
- `total_spans`
- `native_span_count`
- `ocr_span_count`
- `region_count`

### `bundle.pages`

Cada pagina debe poder contener:

- `page_number`
- `width`
- `height`
- `native_text`
- `ocr_text`
- `reading_text`
- `spans`

### `bundle.spans`

Cada span debe poder contener:

- `span_id`
- `page`
- `text`
- `bbox`
- `source`
- `engine`
- `block_no`
- `line_no`
- `confidence`

### `bundle.regions`

Cada region debe poder contener:

- `region_id`
- `region_type`
- `page`
- `bbox`
- `text`
- `span_ids`
- `confidence`

### `bundle.candidate_groups`

Es espacio estable para candidatos previos a la resolucion final.

Cada candidato debe poder contener:

- `candidate_id`
- `field`
- `value`
- `source`
- `extractor`
- `page`
- `region_type`
- `bbox`
- `score`

Regla:

- el resolvedor no debe depender del formato crudo del proveedor OCR
- el resolvedor debe trabajar sobre el bundle interno

---

## 5. Salida estable del motor

La respuesta del motor debe incluir, como minimo:

- `contract`
- `engine_request`
- `success`
- `normalized_document`
- `document_input`
- `field_confidence`
- `coverage`
- `evidence`
- `decision_flags`
- `company_match`
- `processing_trace`
- `raw_text`
- `method`
- `provider`
- `pages`
- `warnings`

Compatibilidad temporal adicional:

- `legacy_data`
- campos legacy aplanados en top-level mientras el backend siga necesitando `numero_factura`, `proveedor`, `total`, etc.
- el backend debe adaptar ese contrato a su persistencia temporal mediante una capa adaptadora, no acoplando directamente el motor a las tablas del MVP

Regla:

- cualquier consumidor nuevo debe apoyarse en `normalized_document`
- los campos legacy quedan como capa de transicion

---

## 6. Payload principal: `normalized_document`

Este es el contrato de negocio estable de la fase actual.

Debe incluir, como minimo:

- `document_meta`
- `classification`
- `identity`
- `issuer`
- `recipient`
- `totals`
- `tax_breakdown`
- `withholdings`
- `line_items`
- `payment_info`
- `import_export_info`

## 6.1 `document_meta`

Debe incluir, como minimo:

- `document_id`
- `advisory_id`
- `company_id`
- `source_channel`
- `input_kind`
- `text_source`
- `file_name`
- `mime_type`
- `page_count`
- `ocr_engine`
- `preprocessing_steps`
- `extraction_provider`
- `extraction_method`
- `extraction_confidence`
- `warnings`
- `raw_text_excerpt`

## 6.2 `classification`

La clasificacion debe salir de un resolvedor semantico comun del motor, no de heuristicas repartidas entre varios modulos.
Esto implica que `document_type`, `invoice_side`, `operation_kind`, `is_rectificative` e `is_simplified`
deben resolverse de forma coherente entre si y alineadas con `company_match`.

Debe incluir, como minimo:

- `document_type`
- `invoice_side`
- `operation_kind`
- `is_rectificative`
- `is_simplified`
- `duplicate_candidate`

## 6.3 `identity`

Debe incluir, como minimo:

- `series`
- `invoice_number`
- `issue_date`
- `operation_date`
- `due_date`
- `period_start`
- `period_end`
- `rectified_invoice_number`
- `order_reference`
- `delivery_note_reference`
- `contract_reference`

## 6.4 `issuer` y `recipient`

Cada uno debe poder contener:

- `name`
- `legal_name`
- `tax_id`
- `vat_id`
- `country`
- `address`
- `postal_code`
- `city`
- `province`
- `email`
- `phone`
- `iban`

## 6.5 `totals`

Debe incluir, como minimo:

- `currency`
- `exchange_rate`
- `subtotal`
- `discount_total`
- `surcharge_total`
- `tax_total`
- `withholding_total`
- `total`
- `amount_due`

## 6.6 `tax_breakdown`

Cada item debe poder contener:

- `tax_regime`
- `tax_code`
- `rate`
- `taxable_base`
- `tax_amount`
- `deductible_percent`
- `is_exempt`
- `is_not_subject`
- `reverse_charge`
- `notes`

## 6.7 `withholdings`

Cada item debe poder contener:

- `withholding_type`
- `rate`
- `taxable_base`
- `amount`

## 6.8 `line_items`

Cada item debe poder contener:

- `line_no`
- `description`
- `quantity`
- `unit_price`
- `discount_amount`
- `line_base`
- `tax_regime`
- `tax_code`
- `tax_rate`
- `tax_amount`
- `line_total`
- `category_hint`
- `account_hint`
- `product_code`
- `confidence`

---

## 7. Semantica de evidencia y resolucion

La evidencia no es decorativa.
Es parte del contrato de seguridad operativa del motor.

## 7.1 Estructura por campo

`evidence` debe ser un mapa por campo.

Cada item de evidencia debe poder incluir:

- `field`
- `value`
- `value_kind`
- `source`
- `extractor`
- `is_final`
- `requires_review`
- `page`
- `bbox`
- `score`
- `text`

## 7.2 Significado de `value_kind`

### `observed`

El valor fue visto directamente en una fuente documental u OCR.

Ejemplos:

- texto PDF nativo
- OCR local
- OCR externo
- candidato de layout

### `resolved`

El valor es el resultado final elegido por el resolvedor entre varios candidatos o tras reconciliacion global.

No implica necesariamente inferencia.
Implica que el motor lo selecciono como valor final.

### `inferred`

El valor no pudo leerse con suficiente claridad y fue deducido por coherencia matematica, fiscal o contextual.

Ejemplos validos:

- inferir cuota IGIC desde base y porcentaje
- inferir porcentaje desde base y total
- inferir contraparte por company match cuando el OCR es ambiguo

Regla:

- todo valor `inferred` debe bajar confianza
- todo valor `inferred` debe quedar trazado en evidencia
- si el campo es sensible, tambien debe activar revision

---

## 8. Cobertura, confianza y revision

El motor debe devolver:

- `field_confidence`
- `coverage`
- `decision_flags`

Regla de producto:

- el motor puede inferir
- el motor no debe inventar
- si no hay suficiente evidencia, debe marcar revision

`coverage` mide presencia de campos criticos.
`field_confidence` mide fiabilidad por campo.
`decision_flags` explica por que conviene revisar.

---

## 9. Compatibilidad temporal con el MVP

Mientras siga vivo el MVP actual, el motor seguira exponiendo:

- `legacy_data`
- y los campos legacy aplanados en top-level

Ejemplos de campos legacy:

- `numero_factura`
- `fecha`
- `proveedor`
- `cif_proveedor`
- `cliente`
- `cif_cliente`
- `base_imponible`
- `iva`
- `iva_porcentaje`
- `retencion`
- `retencion_porcentaje`
- `total`
- `lineas`
- `tipo_factura`

Regla:

- los consumidores nuevos no deben construirse sobre estos campos
- el backend actual puede seguir usandolos mientras dure la transicion

---

## 10. Lo contable sigue fuera del contrato principal

En esta fase no se cierra como contrato estable:

- `accounting_proposal`
- `validated_result`
- asientos finales
- integracion ERP

Eso podra existir despues, pero no debe condicionar el motor documental.

---

## 11. Resultado esperado de la Fase 1

La Fase 1 se considerara cerrada cuando:

- documentacion y modelos reflejen este contrato
- exista version explicita del contrato
- el `ai-service` siga siendo compatible con el backend actual
- quede separada la salida estable de la salida legacy
