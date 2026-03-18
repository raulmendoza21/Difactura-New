# Difactura - Modelo de datos del MVP documental

## 1. Objetivo de esta fase

En la primera fase no vamos a modelar todavia toda la contabilidad.

El modelo de datos se centra en:

- contexto de asesoria
- empresas cliente
- documentos recibidos
- trabajos de procesamiento
- resultados extraidos
- revision humana
- auditoria

---

## 2. Entidades minimas del MVP

## 2.1 Asesoria

Representa el tenant principal del sistema en esta fase.

Campos sugeridos:

- id
- nombre
- estado
- created_at

## 2.2 EmpresaCliente

Empresa para la que trabaja la asesoria.

Campos sugeridos:

- id
- asesoria_id
- nombre
- nombre_normalizado
- cif
- estado
- created_at

## 2.3 Usuario

Usuario interno de la asesoria.

Campos sugeridos:

- id
- asesoria_id
- email
- password_hash
- nombre
- rol
- activo
- created_at

## 2.4 DocumentoFactura

Registro principal del documento recibido.

Campos sugeridos:

- id
- asesoria_id
- empresa_cliente_id
- usuario_subida_id
- estado
- canal_entrada
- nombre_original
- mime_type
- tamano_bytes
- hash_archivo
- storage_key
- pages
- uploaded_at
- last_processed_at

Estados sugeridos:

- recibido
- almacenado
- en_cola
- procesando
- procesado
- pendiente_revision
- aceptado
- rechazado
- error

## 2.5 ProcessingJob

Trabajo tecnico asociado al documento.

Campos sugeridos:

- id
- documento_id
- tipo
- estado
- prioridad
- retry_count
- started_at
- finished_at
- error_message
- worker_name

## 2.6 ExtractionResult

Snapshot del resultado automatico.

Campos sugeridos:

- id
- documento_id
- version
- metodo
- proveedor_detectado
- numero_factura
- fecha_factura
- base_imponible
- impuesto
- total
- moneda
- tipo_documento
- confianza
- warnings_json
- raw_payload_json
- created_at

## 2.7 ReviewDecision

Decision humana de la asesoria sobre la captura.

Campos sugeridos:

- id
- documento_id
- usuario_id
- decision
- comentarios
- corrected_payload_json
- decided_at

Decisiones sugeridas:

- aceptar
- rechazar
- reprocesar

## 2.8 DuplicateCandidate

Relacion entre documentos potencialmente duplicados.

Campos sugeridos:

- id
- documento_id
- documento_relacionado_id
- score
- motivo
- created_at

## 2.9 AuditEvent

Registro de acciones importantes.

Campos sugeridos:

- id
- asesoria_id
- actor_usuario_id
- entidad_tipo
- entidad_id
- accion
- detalle_json
- created_at

---

## 3. Relaciones principales

- una asesoria tiene muchos usuarios
- una asesoria tiene muchas empresas cliente
- una empresa cliente tiene muchos documentos
- un documento tiene muchos jobs
- un documento puede tener varios resultados de extraccion
- un documento puede tener una decision final de revision
- un documento puede tener varios candidatos a duplicado

---

## 4. Lo que se deja para la fase contable

Estas entidades no hacen falta todavia como parte del nucleo del MVP:

- AsientoContable
- AsientoLinea
- CuentaContable
- Contrapartida
- PropuestaContable completa

Pueden aparecer mas adelante cuando la fase documental este consolidada.

---

## 5. Persistencia documental

Para esta fase la recomendacion es:

- documento binario fuera de la tabla principal
- metadata documental en PostgreSQL

El campo clave es `storage_key`, que apunta al sistema de almacenamiento elegido.

---

## 6. Minimo imprescindible para empezar

Si queremos reducir aun mas el primer corte, el minimo real seria:

- Asesoria
- EmpresaCliente
- Usuario
- DocumentoFactura
- ProcessingJob
- ExtractionResult
- ReviewDecision
- AuditEvent

Con eso ya se puede construir la primera operativa documental seria.
