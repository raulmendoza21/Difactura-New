# Difactura - Hito 1: contexto de asesoria y empresa cliente

## 1. Objetivo del hito

El objetivo de este hito es dejar resuelto el contexto funcional minimo para operar como asesoria.

Al terminar este corte, el sistema debe permitir:

1. iniciar sesion con un usuario interno de asesoria
2. conocer a que asesoria pertenece ese usuario
3. listar solo las empresas cliente de esa asesoria
4. seleccionar una empresa cliente activa para trabajar
5. usar esa seleccion en los modulos posteriores de subida y bandeja

Este hito no incluye todavia:

- subida multiple
- jobs y cola
- OCR o extraccion
- revision documental
- contabilidad

---

## 2. Decisiones funcionales para arrancar

Para no bloquear el avance, en este hito fijamos estas decisiones:

- el usuario autenticado pertenece a una sola asesoria
- una empresa cliente tambien pertenece a una sola asesoria
- la seleccion de empresa cliente sera una seleccion de contexto en frontend
- esa seleccion viajara al backend en los endpoints que lo necesiten
- no vamos a persistir aun una "empresa activa por usuario" en base de datos

Esto simplifica mucho el arranque y evita modelar demasiado pronto preferencias de usuario.

---

## 3. Estado actual del repo que podemos reutilizar

## Backend

Ya existe:

- login con JWT
- endpoint `/auth/login`
- endpoint `/auth/me`
- `authMiddleware`
- rutas protegidas
- tabla `usuarios`
- tabla `clientes`

Limitaciones del estado actual:

- el usuario no pertenece a una asesoria
- los clientes no estan aislados por asesoria
- `auth/me` no devuelve contexto de tenant
- `customerRoutes` no filtra por asesoria

## Frontend

Ya existe:

- `AuthContext`
- login funcional
- rutas protegidas
- layout principal

Limitaciones del estado actual:

- el contexto global solo guarda `user`
- no existe seleccion global de empresa cliente
- la UI esta pensada todavia alrededor del flujo heredado de facturas

## Database

Ya existe un esquema operativo, pero esta orientado al modelo anterior:

- `usuarios`
- `clientes`
- `facturas`
- `processing_jobs`

Limitaciones del estado actual:

- no existe `asesorias`
- no existe relacion fuerte `usuarios -> asesoria`
- no existe relacion fuerte `clientes -> asesoria`

## AI service

En este hito no necesita cambios funcionales.

Solo debe quedar claro que no participa todavia en el contexto de asesoria.

---

## 4. Tareas tecnicas por modulo

## 4.1 `database/`

Objetivo:
redefinir el modelo minimo para soportar multiempresa bajo una asesoria.

Tareas:

- crear tabla `asesorias`
- anadir `asesoria_id` a `usuarios`
- sustituir o adaptar `clientes` para que represente `empresas_cliente`
- anadir `asesoria_id` a `clientes`
- definir restricciones de integridad:
  - un usuario debe pertenecer a una asesoria
  - una empresa cliente debe pertenecer a una asesoria
- crear indices utiles:
  - `usuarios(asesoria_id, email)`
  - `clientes(asesoria_id, nombre_normalizado)`
  - `clientes(asesoria_id, cif)`
- actualizar seed inicial con:
  - una asesoria de ejemplo
  - usuarios de esa asesoria
  - varias empresas cliente de esa asesoria

Decision de implementacion:

- para el primer corte, es aceptable reutilizar la tabla `clientes` y reinterpretarla como `empresa cliente`
- si luego molesta la nomenclatura, ya haremos migracion o renombre en otro hito

Definicion de terminado:

- la base puede devolver usuarios con asesoria
- la base puede devolver empresas cliente filtradas por asesoria

## 4.2 `backend/src/config` y `backend/src/middleware`

Objetivo:
hacer que el contexto de asesoria quede disponible en toda peticion autenticada.

Tareas:

- extender el JWT para incluir `asesoria_id`
- actualizar `authMiddleware` para validar y propagar `asesoria_id`
- decidir convencion de contexto de empresa cliente en request
  - opcion recomendada: `x-company-id` o `company_id` en query/body segun endpoint
- crear middleware ligero de validacion de empresa cliente cuando aplique

Definicion de terminado:

- cualquier ruta autenticada puede saber que asesoria opera
- las rutas que trabajan con empresa cliente validan que pertenece a la asesoria del usuario

## 4.3 `backend/src/repositories`

Objetivo:
llevar el acceso a datos al nuevo dominio minimo.

Tareas:

- crear o adaptar `advisoryRepository`
- adaptar `customerRepository` para:
  - listar por `asesoria_id`
  - buscar por `id` y `asesoria_id`
  - buscar por `cif` dentro de la asesoria
- adaptar repositorio de usuarios para devolver `asesoria_id`
- evitar queries globales sin filtro de tenant

Definicion de terminado:

- no quedan accesos a empresas cliente sin filtro por asesoria en rutas del Hito 1

## 4.4 `backend/src/controllers`, `services`, `routes` y `validators`

Objetivo:
exponer API minima de autenticacion y empresas cliente con semantica nueva.

Tareas:

- actualizar `authController.login`
  - devolver `user`
  - devolver `advisory`
- actualizar `authController.me`
  - incluir asesoria del usuario
- revisar `authRoutes` para mantener solo lo necesario en MVP
- adaptar `customerRoutes` a semantica de empresas cliente
- si hace falta, renombrar mentalmente la ruta a `/companies` aunque internamente siga usando `customerRoutes`
- crear contrato estable para:
  - `GET /api/auth/me`
  - `GET /api/companies`
  - `GET /api/companies/:id`

Campos minimos de respuesta:

- usuario:
  - `id`
  - `nombre`
  - `email`
  - `rol`
- asesoria:
  - `id`
  - `nombre`
- empresa cliente:
  - `id`
  - `nombre`
  - `cif`
  - `estado`

Definicion de terminado:

- login devuelve contexto completo
- el frontend puede cargar empresas cliente reales tras autenticarse

## 4.5 `frontend/src/context`

Objetivo:
guardar el contexto global del usuario de asesoria.

Tareas:

- ampliar `AuthContext` para guardar:
  - `user`
  - `advisory`
  - `selectedCompany`
- cargar `advisory` desde login o `auth/me`
- exponer acciones:
  - `setSelectedCompany`
  - `clearSelectedCompany`
- persistir `selectedCompany` en `localStorage` mientras no tengamos algo mas sofisticado

Definicion de terminado:

- al refrescar la app, se conserva el contexto basico del usuario
- la empresa seleccionada sigue disponible entre pantallas

## 4.6 `frontend/src/services`

Objetivo:
conectar el frontend con el nuevo contexto de empresas cliente.

Tareas:

- crear `companyService`
- mantener `authService` alineado con la respuesta nueva del backend
- anadir helpers para obtener lista de empresas cliente
- si se usa `selectedCompany` en requests posteriores, preparar helper para inyectarlo

Definicion de terminado:

- el frontend puede autenticar, consultar `me` y cargar empresas cliente sin codigo duplicado

## 4.7 `frontend/src/components` y `pages`

Objetivo:
hacer visible el contexto de asesoria y la seleccion de empresa cliente.

Tareas:

- actualizar login para soportar la nueva respuesta
- crear selector de empresa cliente reutilizable
- mostrar la asesoria actual en `Navbar` o en el layout
- decidir en que pantalla vive primero la seleccion:
  - opcion recomendada: `Dashboard`
  - con reflejo posterior en `Navbar`
- bloquear modulos futuros si no hay empresa cliente seleccionada

Pantallas a tocar primero:

- `pages/Login.jsx`
- `pages/Dashboard.jsx`
- `components/common/Navbar.jsx`
- `components/auth/ProtectedRoute.jsx` solo si hace falta para roles

Definicion de terminado:

- un usuario entra
- ve su asesoria
- elige una empresa cliente
- la app mantiene ese contexto visible

## 4.8 `ai-service/`

Objetivo:
dejar explicitamente este modulo fuera del trabajo activo del Hito 1.

Tareas:

- ninguna funcional para este hito
- solo revisar que no haya dependencias fuertes con entidades antiguas de cliente/factura que bloqueen el Hito 2

Definicion de terminado:

- `ai-service` no condiciona el avance del contexto de asesoria

---

## 5. Orden de implementacion recomendado

Orden realista de trabajo:

1. `database/`
   - asesorias
   - usuarios con `asesoria_id`
   - clientes filtrables por asesoria
   - seeds
2. `backend/`
   - login y `me` con contexto
   - repositorios y rutas de empresas cliente
   - validaciones de pertenencia
3. `frontend/`
   - `AuthContext`
   - servicios
   - selector de empresa cliente
   - visibilidad del contexto en layout
4. prueba de flujo extremo a extremo
   - login
   - `me`
   - listado de empresas
   - seleccion persistida

---

## 6. Criterios de aceptacion

El Hito 1 se da por bueno cuando ocurre esto:

1. un usuario inicia sesion
2. el backend responde con `user` y `advisory`
3. el frontend mantiene la sesion y el contexto
4. la app lista solo empresas cliente de su asesoria
5. el usuario selecciona una empresa cliente
6. la seleccion queda disponible para las pantallas siguientes

---

## 7. Riesgos y simplificaciones

Riesgos:

- intentar renombrar demasiadas entidades del modelo antiguo a la vez
- mezclar ya en este hito estados documentales o logica de facturas
- querer resolver multirol completo antes de tiempo

Simplificaciones recomendadas:

- mantener `clientes` como nombre tecnico temporal si acelera
- no tocar aun `facturas`, `processing_jobs` ni `ai-service`
- usar `localStorage` para empresa seleccionada en esta fase

---

## 8. Siguiente paso despues del Hito 1

Cuando este hito este cerrado, el siguiente corte natural es el Hito 2:

- subida multiple
- almacenamiento del documento original
- creacion del lote y metadatos minimos

Ese segundo hito ya debera apoyarse en el contexto de empresa cliente resuelto aqui.
