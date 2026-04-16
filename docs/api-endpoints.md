# Difactura - API alineada con el plan actual

## 1. Objetivo

Este documento describe la API de negocio que encaja con el plan vigente.

La idea actual del sistema es:

- mantener frontend y backend
- desacoplar el motor documental
- usar el backend como cliente del motor
- no cerrar todavia la integracion con la base de datos final de cada empresa

Este documento no intenta definir toda la API futura del producto final.
Solo fija la API que sigue teniendo sentido en la fase actual.

Documento rector:
    
- ver `docs/motor-documental-desacoplado.md`

---

## 2. Principios

- todos los endpoints de negocio cuelgan de `/api`
- autenticacion mediante bearer token
- el backend no expone detalles internos del proveedor OCR
- el backend expone documentos, jobs, revision y resultados normalizados
- el motor documental se consume como servicio interno

---

## 3. Que debe hacer la API en esta fase

La API de negocio debe cubrir:

- autenticacion
- gestion de empresa activa
- subida de documentos
- consulta de documentos y jobs
- reproceso
- revision y validacion
- consulta del resultado normalizado

La API no debe cerrar todavia:

- integracion ERP
- escritura en la base de datos real de la empresa
- asientos contables finales

---

## 4. Endpoints de negocio que siguen vigentes

## 4.1 Autenticacion

### POST `/api/auth/login`

Inicia sesion.

### GET `/api/auth/me`

Devuelve usuario autenticado y contexto basico.

---

## 4.2 Empresas / contexto

### GET `/api/companies`

Lista las empresas disponibles para el usuario o tenant actual.

La empresa activa puede viajar:

- en cabecera
- en query
- en body

La forma exacta puede ajustarse mas adelante, pero el concepto de `empresa activa` sigue vigente.

---

## 4.3 Documentos

### POST `/api/documents/upload`

Sube uno o varios documentos.

Responsabilidad:

- registrar metadata
- guardar el original
- crear un job por documento
- devolver respuesta rapida sin esperar a la extraccion

Campos esperados:

- `company_id`
- `files[]`
- `channel` opcional

### GET `/api/documents`

Lista documentos.

Filtros esperados:

- `company_id`
- `status`
- `search`
- `page`
- `limit`

### GET `/api/documents/:id`

Devuelve el detalle del documento.

Debe incluir, como minimo:

- metadata
- estado
- ultimo job
- resultado documental mas reciente

### GET `/api/documents/:id/file`

Devuelve el archivo original.

### GET `/api/documents/:id/jobs`

Devuelve historial de jobs.

### POST `/api/documents/:id/reprocess`

Reencola el documento.

---

## 4.4 Revision

### GET `/api/review-queue`

Devuelve la bandeja de revision.

### PATCH `/api/documents/:id/extraction`

Permite corregir el resultado antes de validar.

No debe limitarse a campos simples.
Debe aceptar el resultado normalizado o el subconjunto editable que decida la UI.

### POST `/api/documents/:id/accept`

Marca el documento como revisado/aceptado.

### POST `/api/documents/:id/reject`

Marca el documento como rechazado.

---

## 4.5 Operacion

### GET `/api/dashboard/summary`

Resumen operativo.

### GET `/api/health`

Health check del backend.

### GET `/worker/health`

Health check del worker o del motor interno, si se expone.

---

## 5. Resultado documental que la API debe exponer

La API no debe exponer internals del OCR.

Debe exponer el contrato estable del motor, o una adaptacion directa de ese contrato.

El resultado documental debe incluir, como minimo:

- `normalized_document`
- `field_confidence`
- `coverage`
- `evidence`
- `decision_flags`
- `company_match`
- `processing_trace`
- `warnings`

Relacion con:

- `docs/motor-documental-desacoplado.md`
- `docs/contrato-datos-documentales-y-contables.md`

Compatibilidad temporal:

- mientras dure el MVP, el backend puede seguir consumiendo campos legacy aplanados
- cualquier contrato nuevo debe construirse sobre `normalized_document`
- la adaptacion del contrato del motor al esquema actual del MVP debe vivir en una capa adaptadora propia del backend

---

## 5.1 Endpoint interno del motor

Mientras el backend siga hablando con el `ai-service` por HTTP interno, la interfaz interna del motor queda asi:

### POST `/ai/process`

Entrada actual:

- `file`
- `mime_type`
- `company_name`
- `company_tax_id`

Salida estable:

- `contract`
- `engine_request`
- `normalized_document`
- `document_input`
- `field_confidence`
- `coverage`
- `evidence`
- `decision_flags`
- `company_match`
- `processing_trace`
- `warnings`
- `raw_text`
- `provider`
- `method`
- `pages`

Compatibilidad temporal:

- `legacy_data`
- campos legacy aplanados en top-level

Nota de implementacion actual:

- el `ai-service` resuelve internamente un `ExtractionResult`
- `/ai/process` solo serializa ese contrato y mantiene la compatibilidad temporal con el MVP

---

## 6. Estados que siguen teniendo sentido

Estados utiles del documento:

- `recibido`
- `almacenado`
- `en_cola`
- `procesando`
- `pendiente_revision`
- `aceptado`
- `rechazado`
- `error`

Estados del job:

- `pendiente`
- `en_proceso`
- `completado`
- `error`

La nomenclatura concreta puede variar en la implementacion, pero el modelo funcional sigue siendo este.

---

## 7. Limites de esta fase

Este documento no cierra todavia:

- endpoints ERP
- endpoints de asientos finales
- endpoints de sincronizacion contable
- endpoints de configuracion contable avanzada

Eso se definira cuando el motor documental este estable y portable.
