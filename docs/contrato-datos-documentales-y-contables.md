# Difactura - Contrato de datos documentales y contables

## 1. Objetivo

Antes de construir la capa contable, el proyecto necesita un contrato de datos estable.

La idea es separar claramente:

- lo que se extrae del documento
- lo que se normaliza fiscalmente
- lo que se propone contablemente
- lo que finalmente valida una persona

Si estas capas se mezclan, la extraccion se vuelve fragil y la contabilidad queda acoplada a OCR.

---

## 2. Referencias oficiales que condicionan el contrato

El diseno debe respetar, como minimo, estos marcos:

- Reglamento de facturacion en Espana:
  - Real Decreto 1619/2012
  - datos obligatorios de factura completa, simplificada y rectificativa
  - fuente: https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696
- IGIC en Canarias:
  - informacion general y modelos de autoliquidacion de la Agencia Tributaria Canaria
  - modelos relevantes para el proyecto: 420 trimestral y 425 resumen anual
  - fuente: https://www3.gobiernodecanarias.org/tributos/atc/w/igic-impuesto-general-indirecto-canario-
- Tipos del IGIC vigentes tras la modificacion aplicable desde 2026:
  - estructura de tipos 0, 1, 3, 5, 7, 9.5, 15 y 20
  - fuente legal: https://www.gobiernodecanarias.org/boc/2025/256/4414.html
- Plan General de Contabilidad:
  - base para escenarios y cuentas contables
  - fuente: https://www.boe.es/buscar/act.php?id=BOE-A-2007-19884

Estas fuentes no obligan a que el sistema resuelva toda la contabilidad automaticamente, pero si condicionan que datos deben existir y que variantes documentales deben contemplarse.

---

## 3. Principio de modelado

No se debe usar un unico JSON para todo.

El contrato recomendado del sistema se divide en 4 niveles:

1. `document_extracted`
2. `document_normalized`
3. `accounting_proposal`
4. `validated_result`

### 3.1 `document_extracted`

Representa lo que sale del OCR y de la IA documental.

Puede contener huecos, incertidumbre y texto sucio.

### 3.2 `document_normalized`

Representa la factura ya interpretada con estructura fiscal y de negocio.

Debe ser el contrato base para:

- validaciones
- deteccion de duplicados
- UI de revision
- generacion de propuesta contable

### 3.3 `accounting_proposal`

Representa el borrador de asiento generado por reglas y ayudas de IA.

Debe ser editable y trazable.

### 3.4 `validated_result`

Representa el resultado final confirmado por humano.

Es el unico que deberia acabar generando asiento confirmado o exportacion contable.

---

## 4. Estructura de `document_normalized`

## 4.1 `document_meta`

Metadatos tecnicos del documento:

- `document_id`
- `advisory_id`
- `company_id`
- `source_channel`
  - `web`
  - `mobile`
  - `camera`
  - `email`
  - `api`
- `file_name`
- `mime_type`
- `page_count`
- `language`
- `ocr_engine`
- `extraction_provider`
- `extraction_method`
- `extraction_confidence`
- `warnings`
- `raw_text_excerpt`

## 4.2 `classification`

Clasificacion documental y funcional:

- `document_type`
  - `desconocido`
  - `factura_completa`
  - `factura_simplificada`
  - `factura_rectificativa`
  - `abono`
  - `ticket`
  - `proforma`
  - `dua`
  - `otro`
- `invoice_side`
  - `recibida`
  - `emitida`
  - `desconocida`
- `operation_kind`
  - `compra`
  - `venta`
  - `gasto`
  - `ingreso`
  - `inmovilizado`
  - `mercaderia`
  - `servicio`
  - `anticipo`
  - `importacion`
  - `intracomunitaria`
  - `desconocida`
- `is_rectificative`
- `is_simplified`
- `duplicate_candidate`

## 4.3 `identity`

Identidad y referencias del documento:

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

## 4.4 `issuer`

Parte emisora:

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

## 4.5 `recipient`

Parte receptora:

- mismos campos que `issuer`

## 4.6 `totals`

Magnitudes economicas:

- `currency`
- `exchange_rate`
- `subtotal`
- `discount_total`
- `surcharge_total`
- `tax_total`
- `withholding_total`
- `total`
- `amount_due`

## 4.7 `tax_breakdown`

Desglose fiscal estructurado.

Debe existir como lista, porque una factura real puede traer varios tipos o varios regimens.

Cada item deberia poder recoger:

- `tax_regime`
  - `IGIC`
  - `IVA`
  - `AIEM`
  - `EXEMPT`
  - `NOT_SUBJECT`
  - `REVERSE_CHARGE`
  - `IRPF`
  - `UNKNOWN`
- `tax_code`
- `rate`
- `taxable_base`
- `tax_amount`
- `deductible_percent`
- `is_exempt`
- `is_not_subject`
- `reverse_charge`
- `notes`

## 4.8 `withholdings`

Retenciones documentales:

- `withholding_type`
  - `IRPF`
  - `OTHER`
  - `NONE`
- `rate`
- `taxable_base`
- `amount`

## 4.9 `line_items`

Lineas del documento:

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

## 4.10 `payment_info`

Informacion de pago:

- `payment_method`
- `payment_terms`
- `installments`
  - `due_date`
  - `amount`
  - `payment_method`
- `iban`
- `direct_debit`
- `paid_at_issue`

## 4.11 `import_export_info`

Bloque necesario para casos mas complejos:

- `dua_number`
- `customs_date`
- `origin_country`
- `destination_country`
- `intracommunity_operator`
- `aiem_amount`

---

## 5. Estructura de `accounting_proposal`

Este JSON no representa OCR. Representa interpretacion contable.

## 5.1 Datos generales

- `scenario`
  - `factura_recibida_gasto_corriente`
  - `factura_recibida_mercaderias`
  - `factura_recibida_inmovilizado`
  - `factura_emitida_ingreso`
  - `factura_con_retencion`
  - `factura_rectificativa_abono`
  - `factura_exenta`
  - `factura_no_sujeta`
  - `factura_con_inversion_sujeto_pasivo`
  - `adquisicion_intracomunitaria`
  - `importacion_con_dua`
  - `anticipo_cliente`
  - `anticipo_proveedor`
  - `factura_con_varios_tipos`
  - `factura_simplificada`
  - `desconocido`
- `posting_date`
- `document_date`
- `journal_code`
- `concept`
- `tax_regime`
- `confidence`
- `warnings`
- `rule_trace`
- `status`
  - `draft`
  - `reviewed`
  - `validated`

## 5.2 Counterparty

- `role`
  - `supplier`
  - `customer`
  - `other`
- `party_name`
- `party_tax_id`
- `account_code`

## 5.3 Entry lines

Cada linea del asiento deberia incluir:

- `line_no`
- `account_code`
- `account_name`
- `side`
  - `DEBE`
  - `HABER`
- `amount`
- `description`
- `tax_link`
- `analytic_account`
- `cost_center`
- `project_code`
- `maturity_date`
- `source`
  - `RULE`
  - `AI`
  - `MANUAL`

---

## 6. Escenarios contables que deben contemplarse

Aunque el MVP no persista todavia el asiento final, el contrato debe dejar previstos estos escenarios:

- factura recibida con gasto corriente
- factura recibida con compra de mercaderias
- factura recibida con inmovilizado
- factura emitida de ingreso
- factura rectificativa o abono
- factura con retencion de IRPF
- factura con varios tipos impositivos
- factura exenta
- factura no sujeta
- factura con inversion del sujeto pasivo
- adquisicion intracomunitaria
- importacion con DUA
- documento con IGIC
- documento con IVA
- documento con AIEM
- anticipo de cliente
- anticipo a proveedor

---

## 7. Que debe salir del OCR/IA y que debe salir de reglas

## 7.1 Debe salir del OCR/IA

- numero de factura
- fechas
- emisor y receptor
- CIF/NIF
- base, cuota y total
- lineas de documento
- referencias de rectificacion
- informacion de pago si aparece

## 7.2 Debe salir de normalizacion y reglas

- clasificacion documental final
- regimen fiscal interpretado
- desglose fiscal consolidado
- deteccion de duplicado
- hints de categoria
- hints de cuenta contable
- escenario contable

## 7.3 Debe quedar para validacion humana

- cuenta exacta
- contrapartida exacta
- deducibilidad
- ajustes de lineas
- resolucion de casos raros o ambiguos

---

## 8. Gap real de extraccion respecto al estado actual

Hoy el sistema ya extrae razonablemente:

- numero
- fecha
- proveedor
- cliente
- base
- tipo de impuesto simple
- total
- lineas basicas

Pero para cubrir el contrato nuevo, faltara mejorar especialmente:

- deteccion fiable del tipo documental
- separacion entre factura completa, simplificada y rectificativa
- `tax_breakdown` multi-linea
- distincion real entre IGIC, IVA, exenta y no sujeta
- retenciones
- vencimientos
- referencias de factura rectificada
- informacion de importacion y DUA
- hints utiles para contabilidad

---

## 9. Priorizacion recomendada para la mejora de extraccion

### Prioridad 1

Imprescindible para empezar a pensar en asiento:

- `document_type`
- `invoice_side`
- `issue_date`
- `invoice_number`
- `issuer`
- `recipient`
- `totals`
- `tax_breakdown`
- `line_items`

### Prioridad 2

Muy importante para casos reales:

- `withholdings`
- `due_date`
- `rectified_invoice_number`
- `payment_info`
- `duplicate_candidate`

### Prioridad 3

Para escenarios avanzados:

- `dua_number`
- `aiem_amount`
- `intracommunity_operator`
- `analytic_account`
- `cost_center`
- `project_code`

---

## 10. Decision de producto recomendada

La siguiente fase del proyecto no deberia ser "guardar asientos" sin mas.

Deberia ser:

1. cerrar este contrato de datos
2. adaptar la UI de revision a `document_normalized`
3. generar `accounting_proposal` por factura
4. dejar que un humano valide
5. solo entonces persistir el asiento confirmado

Ese orden reduce riesgo y evita que la capa contable se apoye en una extraccion demasiado pobre.
