# Difactura - API del MVP documental

## 1. Objetivo

Este documento define los endpoints minimos de la primera fase del producto.

La API de este MVP cubre:

- autenticacion de usuarios de asesoria
- seleccion de empresa cliente
- subida de documentos
- seguimiento del procesamiento
- bandeja de revision
- aceptacion, rechazo y reproceso

No cubre todavia:

- asientos contables
- contrapartidas
- integraciones con ERP

---

## 2. Convenciones generales

- todos los endpoints de negocio cuelgan de `/api`
- autenticacion mediante bearer token
- todas las acciones quedan asociadas a la asesoria del usuario autenticado
- el contexto de empresa cliente puede ir en el body o por ruta, segun el caso de uso

---

## 3. Endpoints de autenticacion

## POST `/api/auth/login`

Inicia sesion de usuario de asesoria.

Body:

```json
{
  "email": "usuario@asesoria.com",
  "password": "secret"
}
```

Respuesta:

```json
{
  "token": "jwt",
  "user": {
    "id": 1,
    "nombre": "Laura",
    "email": "usuario@asesoria.com",
    "rol": "OPERADOR"
  },
  "advisory": {
    "id": 3,
    "nombre": "Asesoria Central"
  }
}
```

## GET `/api/auth/me`

Devuelve el usuario autenticado y su contexto.

---

## 4. Endpoints de empresas cliente

## GET `/api/companies`

Lista las empresas cliente disponibles para la asesoria.

Respuesta:

```json
{
  "data": [
    {
      "id": 12,
      "nombre": "Empresa Demo SL",
      "cif": "B12345678"
    }
  ]
}
```

---

## 5. Endpoints de documentos

## POST `/api/documents/upload`

Sube uno o varios documentos y crea un job por cada uno.

Request:

- `multipart/form-data`
- `company_id`
- `files[]`
- `channel` opcional: `web`, `mobile_camera`, `mobile_gallery`

Respuesta:

```json
{
  "success": true,
  "batch_id": "upl_20260318_001",
  "documents": [
    {
      "id": 101,
      "estado": "en_cola"
    },
    {
      "id": 102,
      "estado": "en_cola"
    }
  ]
}
```

## GET `/api/documents`

Lista documentos con filtros.

Filtros previstos:

- `company_id`
- `status`
- `from`
- `to`
- `search`
- `page`
- `limit`

## GET `/api/documents/:id`

Devuelve detalle del documento:

- metadata
- estado
- resultado de extraccion mas reciente
- duplicados
- decision de revision si existe

## GET `/api/documents/:id/file`

Devuelve el archivo original para previsualizacion o descarga.

## GET `/api/documents/:id/jobs`

Devuelve el historial de jobs del documento.

## POST `/api/documents/:id/reprocess`

Vuelve a encolar el documento.

Respuesta:

```json
{
  "success": true,
  "job_id": 9001,
  "estado": "en_cola"
}
```

---

## 6. Endpoints de bandeja de revision

## GET `/api/review-queue`

Devuelve la bandeja de documentos pendientes de revision.

Filtros previstos:

- `company_id`
- `status`
- `duplicate`
- `page`
- `limit`

Estados utiles:

- `pendiente_revision`
- `procesado`
- `error`
- `rechazado`

## PATCH `/api/documents/:id/extraction`

Permite corregir manualmente los datos extraidos antes de decidir.

Body ejemplo:

```json
{
  "proveedor_detectado": "Proveedor Demo SL",
  "numero_factura": "F-2026-001",
  "fecha_factura": "2026-03-18",
  "base_imponible": 100.0,
  "impuesto": 21.0,
  "total": 121.0
}
```

## POST `/api/documents/:id/accept`

Marca la captura como aceptada por la asesoria.

Body opcional:

```json
{
  "comentarios": "Datos revisados manualmente"
}
```

## POST `/api/documents/:id/reject`

Marca la captura como rechazada.

Body:

```json
{
  "motivo": "Documento ilegible"
}
```

---

## 7. Endpoints de soporte operativo

## GET `/api/dashboard/summary`

Resumen operativo basico:

- documentos recibidos
- en cola
- procesando
- pendientes de revision
- rechazados

## GET `/api/health`

Health check del API principal.

## GET `/worker/health`

Health check del worker o del servicio de extraccion, si se expone por separado.

---

## 8. Estados documentales recomendados

Estados minimos:

- `recibido`
- `almacenado`
- `en_cola`
- `procesando`
- `procesado`
- `pendiente_revision`
- `aceptado`
- `rechazado`
- `error`

---

## 9. Contrato de datos minimo del resultado de extraccion

El resultado de extraccion del MVP debe poder representar, como minimo:

```json
{
  "proveedor_detectado": "Proveedor Demo SL",
  "numero_factura": "F-2026-001",
  "fecha_factura": "2026-03-18",
  "base_imponible": 100.0,
  "impuesto": 21.0,
  "total": 121.0,
  "moneda": "EUR",
  "tipo_documento": "factura",
  "confianza": 0.84,
  "warnings": [
    "possible_duplicate",
    "tax_id_missing"
  ]
}
```

---

## 10. Lo que se deja para la fase contable

No se definen aun endpoints para:

- asientos
- cuentas contables
- contrapartidas
- exportaciones a software contable

Esos contratos se definiran cuando la fase documental este estable.
