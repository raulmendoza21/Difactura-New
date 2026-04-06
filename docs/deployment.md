# Difactura - Despliegue alineado con el plan actual

## 1. Objetivo

Este documento describe el despliegue que encaja con el plan vigente.

La arquitectura actual de desarrollo puede seguir usando Docker local.
La arquitectura objetivo de produccion no debe depender de un solo servidor con todo junto.

Documento rector:

- ver `docs/motor-documental-desacoplado.md`

---

## 2. Principio de despliegue

La regla base es:

- el frontend recibe
- el backend registra
- la cola distribuye
- el worker procesa
- el motor documental resuelve

El usuario no debe esperar a que termine el OCR para poder seguir operando.

---

## 3. Piezas del sistema en produccion

Servicios recomendados:

- `frontend`
- `backend-api`
- `queue`
- `worker`
- `ai-service`
- `postgresql`
- `object-storage`
- `ocr/document parser externo`
- `fallback llm externo`

---

## 4. Que es publico y que es privado

## 4.1 Servicios publicos

- `frontend`
- `backend-api`

## 4.2 Servicios privados

- `queue`
- `worker`
- `ai-service`
- `postgresql`
- `object-storage`

## 4.3 Servicios externos

- OCR principal por API
- fallback por API

El `ai-service` no deberia exponerse publicamente si no hace falta.

---

## 5. Responsabilidades por servicio

## 5.1 `frontend`

- subida
- bandeja
- detalle
- revision
- validacion

## 5.2 `backend-api`

- auth
- empresa activa
- jobs
- auditoria
- consulta de resultados
- adaptacion temporal al modelo del MVP

## 5.3 `queue`

- desacoplar la subida del procesamiento
- reintentos
- recuperacion basica
- reparto de carga

## 5.4 `worker`

- consumir jobs
- descargar el documento
- invocar el `ai-service`
- persistir resultado a traves del backend o repositorio correspondiente

## 5.5 `ai-service`

- clasificacion de entrada
- cliente del proveedor documental
- bundle interno
- generacion de candidatos
- resolvedor global
- confianza
- fallback selectivo

## 5.6 `postgresql`

- metadata documental
- estados
- jobs
- auditoria
- resultados documentales

## 5.7 `object-storage`

- documentos originales
- acceso por frontend para previsualizacion
- acceso por worker para procesamiento

---

## 6. Entorno local

En local se sigue usando `docker compose`.

Comandos actuales de referencia:

- levantar: `docker compose --profile doc-ai-text up -d --build`
- apagar: `docker compose --profile doc-ai-text down`

En local, Docker sigue sirviendo para:

- probar frontend, backend y ai-service juntos
- reprocesar documentos reales
- correr benchmark y regresiones
- validar cambios del motor antes de tocar produccion

---

## 7. Regla de escalado

El escalado importante no es el del frontend.
Es el del procesamiento.

Debe ser posible:

- tener varias asesorias subiendo a la vez
- tener miles de documentos pendientes
- escalar workers sin tocar frontend
- escalar backend sin tocar el motor
- cambiar de proveedor OCR sin rehacer el despliegue completo

---

## 8. Almacenamiento documental

La direccion objetivo es:

- originales en `object storage`
- metadata en `postgresql`

No se debe tratar el filesystem local del contenedor como almacenamiento final del producto.

---

## 9. Observabilidad minima

Debe existir, como minimo:

- health checks
- logs por job
- estado visible por documento
- errores persistidos
- auditoria
- trazabilidad de proveedor y metodo de extraccion

---

## 10. Lo que no se cierra todavia

Este documento no cierra:

- proveedor cloud final concreto
- proveedor de cola final concreto
- proveedor de object storage final concreto
- integracion con ERP
- estrategia final de persistencia de empresa

Lo que si deja claro es la separacion de responsabilidades y el modelo de despliegue.

---

## 11. Activacion de Mistral en esta etapa

La integracion actual queda preparada para activarse por configuracion.

Configuracion minima esperada:

- `document_parser_provider=mistral`
- `mistral_api_key=...`

Configuracion opcional:

- `document_parser_force_provider`
- `document_parser_fallback_enabled`
- `document_parser_fallback_provider`
- `doc_ai_enabled`
- `doc_ai_provider`
- `doc_ai_selective_enabled`
- `doc_ai_fallback_confidence_threshold`
- `doc_ai_fallback_missing_required_threshold`
- `doc_ai_fallback_warning_threshold`
- `mistral_base_url`
- `mistral_ocr_model`
- `mistral_file_visibility`
- `mistral_extract_header`
- `mistral_extract_footer`
- `mistral_table_format`

Regla operativa actual:

- si `document_parser_provider=mistral` y hay API key, Mistral pasa a ser la ruta principal
- si Mistral falla en runtime, el loader cae al proveedor local para no bloquear el flujo
- `docker-compose` ya expone estas variables en `ai-service`, y `.env` queda preparado con `document_parser_provider=mistral`
- si `document_parser_force_provider=local`, se fuerza la ruta local para depuracion o comparativas
- si `doc_ai_enabled=true`, el segundo motor queda disponible solo como fallback selectivo
- si `doc_ai_selective_enabled=false`, el segundo motor vuelve a poder ejecutarse siempre
