# Difactura — Documentación Técnica del Proyecto

## Índice

1. [Objetivo y problema que resuelve](#1-objetivo-y-problema-que-resuelve)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Frontend (React)](#3-frontend-react)
4. [Backend (Node.js)](#4-backend-nodejs)
5. [Pipeline de procesamiento documental (Python)](#5-pipeline-de-procesamiento-documental-python)
6. [Base de datos (PostgreSQL)](#6-base-de-datos-postgresql)
7. [Integración con la BD empresarial](#7-integración-con-la-bd-empresarial)
8. [Seguridad](#8-seguridad)
9. [Roles y permisos](#9-roles-y-permisos)
10. [Nginx (Reverse Proxy)](#10-nginx-reverse-proxy)
11. [Storage (Almacenamiento)](#11-storage-almacenamiento)
12. [Docker y entornos](#12-docker-y-entornos)
13. [Monitorización y observabilidad](#13-monitorización-y-observabilidad)
14. [Flujo completo de una factura](#14-flujo-completo-de-una-factura)
15. [Fases de implantación (Roadmap)](#15-fases-de-implantación-roadmap)
16. [Riesgos y mitigaciones](#16-riesgos-y-mitigaciones)
17. [Beneficios para la empresa](#17-beneficios-para-la-empresa)
18. [Resumen de tecnologías](#18-resumen-de-tecnologías)

---

## 1. Objetivo y problema que resuelve

### El problema

En cualquier empresa, la gestión de facturas implica:

- Recibir facturas en PDF, imagen escaneada o papel.
- Leer manualmente cada factura para extraer los datos clave.
- Introducir esos datos a mano en el sistema de gestión o contabilidad.
- Verificar que el proveedor existe, que los importes cuadran, que no está duplicada.
- Archivar el documento original.

Este proceso es **lento, repetitivo y propenso a errores humanos**. Una persona puede tardar entre 3 y 10 minutos por factura. Con cientos de facturas al mes, el coste en tiempo es enorme.

### La solución

Difactura es un sistema de gestión inteligente de facturas desarrollado por **Disoft**, que **automatiza la lectura, extracción y validación de datos** mediante un pipeline de procesamiento documental (OCR + reglas + extracción). El sistema:

- Lee facturas en formato PDF o imagen.
- Detecta automáticamente si es factura de compra o de venta.
- Extrae los datos clave (número, fecha, proveedor, importes, líneas de producto...).
- Muestra los datos al usuario para que los revise antes de confirmar.
- Sincroniza la información validada con la base de datos PostgreSQL de la empresa **mediante una capa de sincronización controlada**.
- Mantiene un historial de todas las operaciones con trazabilidad completa.

**La IA nunca escribe directamente en la BD empresarial sin supervisión.** El sistema propone, el humano valida.

### Beneficio clave

Reducir el tiempo de procesamiento de facturas de **minutos a segundos**, manteniendo el control humano sobre los datos contables.

---

## 2. Arquitectura del sistema

El sistema está compuesto por **4 servicios independientes** que se comunican entre sí:

| Servicio | Tecnología | Puerto (desarrollo) | Puerto (producción) | Responsabilidad |
|----------|-----------|---------------------|---------------------|-----------------|
| Frontend | React + Vite | 5173 | 80 (via Nginx) | Interfaz de usuario |
| Backend | Node.js + Express | 3000 | 80 (via Nginx en /api) | API, lógica de negocio, BD |
| Pipeline documental | Python + FastAPI | 8000 | 80 (via Nginx en /ai) | Procesamiento de documentos |
| Base de datos | PostgreSQL | 5432 | 5432 | Persistencia de datos |

```
┌─────────────────────────────────────────────────────────────────┐
│                        NGINX (puerto 80) — solo producción      │
│                         Reverse Proxy                           │
│   /             → Frontend React (build estática)               │
│   /api/*        → Backend Node.js (3000)                        │
│   /ai/*         → Pipeline documental Python (8000)             │
└─────────────────────────────────────────────────────────────────┘
          │                     │                    │
          ▼                     ▼                    ▼
┌───────────────┐   ┌────────────────────┐   ┌────────────────────┐
│   Frontend    │   │      Backend       │   │  Pipeline docum.   │
│    React      │──▶│     Node.js        │──▶│     Python        │
│    Vite       │   │     Express        │   │    FastAPI         │
│   Tailwind    │   │                    │   │  OCR/Extracción    │
└───────────────┘   └────────────────────┘   └────────────────────┘
                            │        │
                            ▼        ▼
                  ┌──────────┐  ┌─────────────────────────┐
                  │BD Difact.│  │ Capa de sincronización  │
                  │ (propia) │  │ con BD empresa (futuro) │
                  └──────────┘  └─────────────────────────┘
```

### Entornos de ejecución

| Entorno | Frontend | Backend | Pipeline | BD |
|---------|----------|---------|----------|-----|
 **Desarrollo** | Vite dev server en puerto 5173 con hot reload | Node.js con nodemon en puerto 3000 | Uvicorn con reload en puerto 8000 | PostgreSQL local o Docker |
| **Producción** | Build estática compilada, servida por Nginx | Node.js en puerto 3000 detrás de Nginx | Uvicorn en puerto 8000 detrás de Nginx | PostgreSQL en servidor o Docker |

**¿Por qué esta separación?**

- Cada servicio se puede escalar, actualizar o reiniciar de forma independiente.
- Si el pipeline falla, el backend sigue funcionando (las facturas quedan en cola).
- Si el frontend cambia, el backend y el pipeline no se ven afectados.
- Python tiene librerías de procesamiento documental y OCR muy superiores a Node.js.
- Node.js es más eficiente para APIs y lógica de negocio que Python.

---

## 3. Frontend (React)

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── index.css
│   ├── assets/
│   │   └── logo.svg
│   ├── components/
│   │   ├── auth/
│   │   │   ├── LoginForm.jsx
│   │   │   └── ProtectedRoute.jsx
│   │   ├── common/
│   │   │   ├── Navbar.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   ├── Footer.jsx
│   │   │   ├── LoadingSpinner.jsx
│   │   │   └── ConfidenceBadge.jsx
│   │   ├── dashboard/
│   │   │   ├── StatsCard.jsx
│   │   │   ├── RecentActivity.jsx
│   │   │   └── Charts.jsx
│   │   └── invoices/
│   │       ├── InvoiceUploader.jsx
│   │       ├── InvoicePreview.jsx
│   │       ├── InvoiceTable.jsx
│   │       ├── InvoiceDetailCard.jsx
│   │       └── InvoiceLineItems.jsx
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── UploadInvoice.jsx
│   │   ├── InvoiceReview.jsx
│   │   ├── InvoiceHistory.jsx
│   │   ├── Dashboard.jsx
│   │   └── NotFound.jsx
│   ├── services/
│   │   ├── api.js
│   │   ├── authService.js
│   │   └── invoiceService.js
│   ├── hooks/
│   │   ├── useAuth.js
│   │   ├── useInvoices.js
│   │   └── useDebounce.js
│   ├── context/
│   │   └── AuthContext.jsx
│   └── utils/
│       ├── formatters.js
│       ├── validators.js
│       └── constants.js
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── index.html
├── .env.example
└── Dockerfile
```

### Archivos de configuración del frontend

| Archivo | Qué es | Por qué existe |
|---------|--------|-----------------|
| `package.json` | Lista de dependencias y scripts de npm | Necesario para instalar React, Vite, Tailwind, Axios, etc. y definir cómo arrancar la app |
| `vite.config.js` | Configuración de Vite (bundler) | Vite es el empaquetador que compila React para desarrollo y producción. Aquí se configura el proxy para no tener problemas de CORS durante desarrollo |
| `tailwind.config.js` | Configuración de Tailwind CSS | Define qué archivos escanea Tailwind para generar solo los estilos que realmente se usan |
| `postcss.config.js` | Configuración de PostCSS | Tailwind necesita PostCSS como procesador de CSS. Es un requisito técnico |
| `index.html` | Página HTML raíz | Es el punto de entrada de la app. Vite inyecta aquí el JavaScript compilado |
| `.env.example` | Variables de entorno de ejemplo | Muestra qué variables hay que configurar (URL del backend, etc.) sin exponer valores reales |
| `Dockerfile` | Instrucciones para crear la imagen Docker del frontend | En producción: compila con Vite y sirve el resultado estático con Nginx. En desarrollo no se usa Docker para el frontend |

### `src/main.jsx`

**Qué hace:** Es el punto de entrada de React. Monta el componente `<App />` dentro del `<div id="root">` del index.html.

**Por qué existe:** React necesita un archivo de arranque que conecte el framework con el DOM del navegador.

### `src/App.jsx`

**Qué hace:** Componente principal que contiene el enrutador (React Router). Define qué página se muestra según la URL.

**Por qué existe:** Centraliza la navegación de toda la aplicación. Aquí se deciden las rutas protegidas (que requieren login) y las públicas. También aplica las restricciones de rol: un usuario con rol `LECTURA` no ve las mismas opciones que uno con rol `ADMIN`.

### `src/index.css`

**Qué hace:** Archivo de estilos globales donde se importan las directivas de Tailwind (`@tailwind base`, etc.).

**Por qué existe:** Tailwind necesita un punto de entrada CSS donde activar sus utilidades.

---

### `src/components/` — Componentes reutilizables

Los componentes son piezas de interfaz que se pueden reusar en distintas páginas.

#### `components/common/` — Componentes compartidos

| Componente | Qué hace | Por qué existe |
|-----------|---------|-----------------|
| `Navbar.jsx` | Barra de navegación superior con el logo, nombre de usuario, rol y opciones | Es el elemento de navegación principal. Aparece en todas las páginas cuando el usuario está logueado. Muestra el rol del usuario activo |
| `Sidebar.jsx` | Menú lateral con los accesos a cada sección (Dashboard, Subir factura, Historial...) | Permite navegar rápidamente entre secciones. Las opciones visibles dependen del rol del usuario |
| `Footer.jsx` | Pie de página con información de la empresa, versión, etc. | Elemento visual que cierra la interfaz. Puede incluir enlaces legales o de soporte |
| `LoadingSpinner.jsx` | Indicador de carga animado (spinner) | Se muestra mientras se espera respuesta del servidor (subida de factura, carga de datos, etc.). Mejora la experiencia del usuario |
| `ConfidenceBadge.jsx` | Etiqueta visual que muestra el nivel de confianza del pipeline (verde ≥90%, amarillo 70-89%, rojo <70%) | Permite al usuario ver de un vistazo si la extracción es fiable o necesita revisión cuidadosa |

#### `components/auth/` — Componentes de autenticación

| Componente | Qué hace | Por qué existe |
|-----------|---------|-----------------|
| `LoginForm.jsx` | Formulario de email y contraseña para iniciar sesión | Es la puerta de entrada al sistema. Sin login no se accede a nada |
| `ProtectedRoute.jsx` | Componente que envuelve rutas y verifica si el usuario está autenticado y tiene el rol necesario | Si alguien intenta acceder a una URL protegida sin estar logueado o sin el rol adecuado, este componente lo redirige. Es un patrón de seguridad estándar en React |

#### `components/invoices/` — Componentes de facturas

| Componente | Qué hace | Por qué existe |
|-----------|---------|-----------------|
| `InvoiceUploader.jsx` | Zona de arrastrar y soltar (drag & drop) para subir archivos PDF o imágenes | Es la interfaz principal de entrada de facturas. Permite subir uno o varios archivos. Valida tipo y tamaño del fichero antes de enviar |
| `InvoicePreview.jsx` | Visor del documento original (PDF o imagen) al lado de los datos detectados | Permite al usuario comparar visualmente lo que dice la factura con lo que el pipeline ha extraído |
| `InvoiceTable.jsx` | Tabla con el listado de facturas procesadas (número, fecha, proveedor, total, estado) | Vista principal del historial. Permite buscar, filtrar por estado y ordenar facturas |
| `InvoiceDetailCard.jsx` | Tarjeta con todos los datos de una factura específica | Muestra la información completa de una factura: datos fiscales, importes, estado de validación, nivel de confianza |
| `InvoiceLineItems.jsx` | Tabla editable con las líneas de producto/servicio de una factura | Una factura puede tener múltiples líneas (productos). Este componente las muestra y permite editarlas antes de confirmar |

#### `components/dashboard/` — Componentes del panel de control

| Componente | Qué hace | Por qué existe |
|-----------|---------|-----------------|
| `StatsCard.jsx` | Tarjeta con un indicador numérico (total facturas, compras del mes, pendientes de revisión, etc.) | Muestra métricas clave de un vistazo. Es el componente base del dashboard |
| `RecentActivity.jsx` | Lista de las últimas acciones realizadas en el sistema | Permite saber rápidamente qué se ha procesado recientemente sin ir al historial completo |
| `Charts.jsx` | Gráficos de barras, líneas o circulares con datos de facturas | Visualización de tendencias: compras vs ventas por mes, proveedores más frecuentes, evolución de gastos |

---

### `src/pages/` — Páginas completas

Las páginas son las vistas que corresponden a cada URL. Cada página usa varios componentes.

| Página | URL | Qué muestra | Roles que acceden | Componentes que usa |
|--------|-----|-------------|-------------------|---------------------|
| `Login.jsx` | `/login` | Pantalla de inicio de sesión | Todos (pública) | `LoginForm` |
| `UploadInvoice.jsx` | `/invoices/upload` | Pantalla para subir facturas | ADMIN, CONTABILIDAD | `InvoiceUploader` |
| `InvoiceReview.jsx` | `/invoices/review/:id` | Revisión de datos detectados por el pipeline | ADMIN, CONTABILIDAD, REVISOR | `InvoicePreview`, `InvoiceDetailCard`, `InvoiceLineItems`, `ConfidenceBadge` |
| `InvoiceHistory.jsx` | `/invoices` | Listado de todas las facturas procesadas | Todos los autenticados | `InvoiceTable` |
| `Dashboard.jsx` | `/dashboard` | Panel principal con métricas y resumen | Todos los autenticados | `StatsCard`, `RecentActivity`, `Charts` |
| `NotFound.jsx` | `/*` | Página de error 404 | Todos | Ninguno especial |

**¿Por qué separar pages de components?**

Las páginas representan rutas completas. Los componentes son piezas reutilizables. Una página agrupa componentes para formar una vista coherente. Si necesitas el mismo componente en dos páginas distintas, no duplicas código.

---

### `src/services/` — Comunicación con el backend

| Archivo | Qué hace | Por qué existe |
|---------|---------|-----------------|
| `api.js` | Configura Axios con la URL base del backend, interceptores de autenticación y manejo de errores | Centraliza toda la configuración HTTP. Si cambia la URL del servidor, solo se toca aquí. Los interceptores adjuntan automáticamente el token JWT a cada petición |
| `authService.js` | Funciones de login, logout, registro y verificación de token | Separa la lógica de autenticación en un módulo claro: `login(email, password)`, `logout()`, `getCurrentUser()` |
| `invoiceService.js` | Funciones para subir facturas, obtener listados, confirmar datos, consultar estado de procesamiento | Centraliza todas las llamadas a la API de facturas: `uploadInvoice(file)`, `getInvoices()`, `confirmInvoice(id, data)`, `getProcessingStatus(id)` |

**¿Por qué no hacer las llamadas HTTP directamente en los componentes?**

Porque si mañana cambias la URL de un endpoint, tendrías que buscar en 20 componentes. Con los services, cambias en un solo sitio.

---

### `src/hooks/` — Custom Hooks

Los hooks son funciones reutilizables que encapsulan lógica de estado y efectos de React.

| Hook | Qué hace | Por qué existe |
|------|---------|-----------------|
| `useAuth.js` | Proporciona acceso al estado de autenticación (usuario actual, rol, si está logueado, funciones de login/logout) | Cualquier componente que necesite saber si el usuario está logueado o qué rol tiene, usa este hook |
| `useInvoices.js` | Gestiona la carga y estado de la lista de facturas (loading, error, datos, polling de estado) | Encapsula la lógica de llamar a la API, manejar el estado de carga y errores. Incluye polling para actualizar el estado de facturas en procesamiento |
| `useDebounce.js` | Retrasa la ejecución de una acción hasta que el usuario deje de escribir | Se usa en búsquedas. Si el usuario escribe "Pro", no quieres hacer 3 peticiones (P, Pr, Pro). Con debounce, solo se busca cuando para de escribir |

---

### `src/context/` — Estado global

| Archivo | Qué hace | Por qué existe |
|---------|---------|-----------------|
| `AuthContext.jsx` | Crea un contexto React que almacena el estado de autenticación (usuario, token, rol) y lo comparte con toda la app | Sin esto, habría que pasar la info del usuario como prop por 10 niveles de componentes. El Context API evita ese problema: cualquier componente accede directamente al estado de autenticación |

---

### `src/utils/` — Utilidades

| Archivo | Qué hace | Por qué existe |
|---------|---------|-----------------|
| `formatters.js` | Funciones para formatear fechas (`12/03/2026`), moneda (`1.452,00 €`), porcentajes (`93%`) | Centraliza el formato de datos. En España se usa coma decimal y punto para miles. Si se cambia de país, se toca solo aquí |
| `validators.js` | Funciones de validación: NIF/CIF válido, email correcto, importe positivo, etc. | Validación en el lado del cliente antes de enviar datos al servidor. Mejora la experiencia y reduce peticiones innecesarias |
| `constants.js` | Constantes de la aplicación: estados de factura, roles de usuario, límites de subida, umbrales de confianza | Evita tener strings "mágicos" repartidos por el código. Si un estado cambia de nombre, se cambia aquí |

---

### `src/assets/`

| Archivo | Qué hace |
|---------|---------|
| `logo.svg` | Logo de la aplicación/empresa en formato vectorial |

---

## 4. Backend (Node.js)

```
backend/
├── src/
│   ├── app.js
│   ├── server.js
│   ├── config/
│   │   ├── database.js
│   │   ├── auth.js
│   │   ├── aiService.js
│   │   └── storage.js
│   ├── controllers/
│   │   ├── authController.js
│   │   ├── invoiceController.js
│   │   ├── supplierController.js
│   │   ├── customerController.js
│   │   ├── productController.js
│   │   └── dashboardController.js
│   ├── routes/
│   │   ├── index.js
│   │   ├── authRoutes.js
│   │   ├── invoiceRoutes.js
│   │   ├── supplierRoutes.js
│   │   ├── customerRoutes.js
│   │   ├── productRoutes.js
│   │   └── dashboardRoutes.js
│   ├── services/
│   │   ├── invoiceService.js
│   │   ├── dbSyncService.js
│   │   ├── aiClientService.js
│   │   ├── supplierService.js
│   │   ├── customerService.js
│   │   ├── auditService.js
│   │   └── validationService.js
│   ├── repositories/
│   │   ├── invoiceRepository.js
│   │   ├── supplierRepository.js
│   │   ├── customerRepository.js
│   │   ├── productRepository.js
│   │   └── auditRepository.js
│   ├── middleware/
│   │   ├── authMiddleware.js
│   │   ├── roleMiddleware.js
│   │   ├── errorHandler.js
│   │   ├── fileUpload.js
│   │   └── requestLogger.js
│   ├── validators/
│   │   ├── invoiceValidator.js
│   │   └── authValidator.js
│   ├── utils/
│   │   ├── helpers.js
│   │   ├── constants.js
│   │   └── errors.js
│   └── database/
│       ├── migrations/
│       └── seeds/
├── package.json
├── nodemon.json
├── .env.example
└── Dockerfile
```

### Archivos raíz del backend

| Archivo | Qué hace | Por qué existe |
|---------|---------|-----------------|
| `src/app.js` | Crea y configura la aplicación Express: carga middleware, registra rutas, configura CORS | Separa la **configuración** de la app del **arranque** del servidor. Así puedes importar la app en tests sin levantar un servidor real |
| `src/server.js` | Arranca el servidor HTTP en el puerto configurado | Punto de entrada real. Importa `app.js`, conecta a la BD y pone el servidor a escuchar |
| `package.json` | Dependencias y scripts del backend | Lista las librerías necesarias (express, pg, jsonwebtoken, multer, axios, bcrypt...) y los scripts de arranque |
| `nodemon.json` | Configuración de nodemon (reinicio automático) | En desarrollo, cuando guardas un archivo, nodemon reinicia el servidor automáticamente. Aquí se configura qué archivos vigilar |
| `.env.example` | Variables de entorno de ejemplo | Documenta las variables necesarias: `DATABASE_URL`, `JWT_SECRET`, `AI_SERVICE_URL`, `PORT` sin exponer valores reales |
| `Dockerfile` | Imagen Docker del backend | Para desplegar el backend como contenedor |

---

### `src/config/` — Configuración

Centraliza toda la configuración del backend en un solo lugar.

| Archivo | Qué configura | Por qué existe |
|---------|--------------|-----------------|
| `database.js` | Conexión a PostgreSQL: host, puerto, usuario, contraseña, nombre de BD, pool de conexiones | Centraliza la conexión a BD. Si cambia el servidor de PostgreSQL, solo se toca aquí. El pool de conexiones permite reutilizar conexiones y no abrir una nueva por cada consulta |
| `auth.js` | Configuración de JWT: secreto, tiempo de expiración del token, algoritmo, configuración de bcrypt | Centraliza los parámetros de autenticación. El JWT (JSON Web Token) es el mecanismo para mantener la sesión del usuario sin guardar estado en el servidor |
| `aiService.js` | URL del servicio de IA, timeout, reintentos, health check | El backend necesita saber dónde está el servicio Python para enviarle las facturas. Aquí se configura la dirección y cuánto esperar antes de dar timeout |
| `storage.js` | Rutas de almacenamiento de archivos, tamaño máximo de subida, tipos permitidos | Define dónde se guardan los PDFs subidos, qué formatos se aceptan (pdf, jpg, png) y el tamaño máximo permitido |

---

### `src/controllers/` — Controladores

Los controladores reciben las peticiones HTTP y devuelven respuestas. Son la **primera capa** que toca la petición después del middleware.

**¿Qué hacen?** Reciben la request, extraen los datos, llaman al service correspondiente y devuelven la response.

**¿Qué NO hacen?** No contienen lógica de negocio ni consultas a la BD. Solo coordinan.

| Controlador | Endpoints que gestiona | Qué hace |
|-------------|----------------------|---------|
| `authController.js` | `POST /login`, `POST /register`, `POST /logout`, `GET /me` | Gestiona el inicio de sesión, registro de usuarios y verificación de identidad |
| `invoiceController.js` | `POST /invoices/upload`, `GET /invoices`, `GET /invoices/:id`, `GET /invoices/:id/status`, `PUT /invoices/:id/confirm`, `PUT /invoices/:id/reject`, `DELETE /invoices/:id` | Gestiona todo el ciclo de vida de una factura: subida, listado, detalle, consulta de estado de procesamiento, confirmación, rechazo y eliminación |
| `supplierController.js` | `GET /suppliers`, `GET /suppliers/:id`, `GET /suppliers/search?q=`, `POST /suppliers`, `PUT /suppliers/:id` | CRUD de proveedores. Incluye búsqueda con matching difuso para evitar duplicados |
| `customerController.js` | `GET /customers`, `GET /customers/:id`, `GET /customers/search?q=`, `POST /customers`, `PUT /customers/:id` | CRUD de clientes. Mismo patrón que proveedores con búsqueda flexible |
| `productController.js` | `GET /products`, `POST /products`, `PUT /products/:id` | CRUD de productos y servicios detectados en las facturas |
| `dashboardController.js` | `GET /dashboard/stats`, `GET /dashboard/recent`, `GET /dashboard/charts` | Devuelve los datos agregados para el panel principal: totales, actividad reciente y datos para gráficos |

---

### `src/routes/` — Definición de rutas

Las rutas conectan URLs con controladores y middleware. También definen **qué rol puede acceder a cada endpoint**.

| Archivo | Qué define | Por qué está separado del controlador |
|---------|-----------|---------------------------------------|
| `index.js` | Agrupa todas las rutas y las exporta como un único router | El `app.js` solo importa este archivo. Mantiene `app.js` limpio |
| `authRoutes.js` | Rutas de `/api/auth/*` | Rutas públicas (login) y protegidas (registro solo para ADMIN) |
| `invoiceRoutes.js` | Rutas de `/api/invoices/*` | Incluye middleware de `fileUpload` y control de roles: subir (ADMIN, CONTABILIDAD), revisar (ADMIN, CONTABILIDAD, REVISOR), ver (todos) |
| `supplierRoutes.js` | Rutas de `/api/suppliers/*` | Protegidas por autenticación. Escritura solo para ADMIN y CONTABILIDAD |
| `customerRoutes.js` | Rutas de `/api/customers/*` | Mismo patrón que suppliers |
| `productRoutes.js` | Rutas de `/api/products/*` | Mismo patrón |
| `dashboardRoutes.js` | Rutas de `/api/dashboard/*` | Rutas de solo lectura, accesibles para todos los roles autenticados |

**¿Por qué separar routes de controllers?**

Las rutas definen **qué URL lleva a qué función**, **qué middleware se aplica** y **qué roles pueden acceder**. Los controladores definen **qué se hace cuando llega esa petición**. Si combinas ambos, el código se hace muy difícil de leer.

---

### `src/services/` — Lógica de negocio

Los servicios contienen las **reglas de la empresa**. Es la capa más importante del backend.

| Servicio | Qué hace | Por qué es necesario |
|----------|---------|---------------------|
| `invoiceService.js` | Lógica completa del procesamiento de facturas: registrar tarea de procesamiento, coordinar con el pipeline, gestionar estados de factura, detectar duplicados, decidir si insert o update | Es el cerebro del sistema. Orquesta todo el flujo: recibe factura → registra job → envía a pipeline → valida resultados → cambia estado |
| `dbSyncService.js` | **Capa de sincronización controlada** con la BD empresarial. Comprueba si un proveedor ya existe, si una factura está duplicada, si los productos coinciden. Nunca escribe directamente en tablas críticas del ERP | Conecta los datos detectados por el pipeline con los datos reales de la empresa. Evita duplicados y mantiene coherencia. **Es la frontera entre Difactura y el sistema real de la empresa** |
| `aiClientService.js` | Cliente HTTP que se comunica con el pipeline Python. Envía el archivo y recibe el JSON con los datos extraídos. Gestiona timeouts y reintentos | Encapsula toda la comunicación con el pipeline. Si mañana cambias de servicio (propio vs Azure Document Intelligence vs Google), solo tocas este archivo |
| `supplierService.js` | Lógica de proveedores: buscar por CIF (prioridad), matching difuso por nombre normalizado, crear nuevos, actualizar datos | Gestiona la lógica de negocio de proveedores. Incluye **normalización de nombres** y **comparación flexible** para evitar duplicados como "Papelería López S.L." vs "PAPELERIA LOPEZ SL" |
| `customerService.js` | Lógica de clientes: buscar por CIF, matching difuso, crear, actualizar | Mismo patrón que proveedores pero para clientes (en facturas de venta) |
| `auditService.js` | Registra cada acción del sistema: quién subió qué factura, quién la confirmó, qué cambió, desde qué IP | Clave para empresa: toda acción queda registrada con usuario, fecha, detalle e IP. Permite rastrear problemas y cumplir normativa |
| `validationService.js` | Reglas de validación de negocio: ¿cuadra el IVA?, ¿la suma de líneas coincide con el total?, ¿el CIF tiene formato válido?, ¿el proveedor existe? | Valida que los datos tengan sentido antes de guardarlos. No es lo mismo validar formato (validator) que validar coherencia de negocio (service) |

#### Matching difuso de proveedores y productos

En facturas reales, un mismo proveedor puede aparecer escrito de muchas formas:

| En factura | En la BD |
|-----------|---------|
| "Papelería López S.L." | "PAPELERIA LOPEZ SL" |
| "Papeleria Lopez" | "PAPELERIA LOPEZ SL" |
| "PAP. LÓPEZ" | "PAPELERIA LOPEZ SL" |

Para evitar crear duplicados, el `supplierService.js` implementa:

1. **Búsqueda por CIF** como prioridad (si viene, es identificador único).
2. **Normalización de nombres**: quitar tildes, pasar a mayúsculas, eliminar "S.L.", "S.A.", puntos, comas.
3. **Comparación flexible** del nombre normalizado si no hay CIF claro.

Esto se aplica también a productos y clientes.

**¿Por qué separar services de controllers?**

El controlador sabe de HTTP (request, response, status codes). El service sabe de **negocio** (facturas, proveedores, IVA). Si pones la lógica en el controlador, no puedes reutilizarla (por ejemplo, si luego quieres procesar facturas por lote sin pasar por HTTP).

---

### `src/repositories/` — Acceso a datos

Los repositorios son la **única capa que habla con PostgreSQL**. Contienen las consultas SQL.

**Todas las consultas usan parámetros preparados** (`$1`, `$2`...) para prevenir inyección SQL.

| Repositorio | Qué gestiona | Ejemplo de funciones |
|-------------|-------------|---------------------|
| `invoiceRepository.js` | Tablas `facturas`, `factura_lineas`, `processing_jobs` | `findById(id)`, `findAll(filters)`, `create(data)`, `update(id, data)`, `findByNumber(numero)`, `createProcessingJob(invoiceId)`, `updateJobStatus(jobId, status)` |
| `supplierRepository.js` | Tabla `proveedores` | `findByCif(cif)`, `findByNormalizedName(name)`, `create(data)`, `update(id, data)` |
| `customerRepository.js` | Tabla `clientes` | `findByCif(cif)`, `findByNormalizedName(name)`, `create(data)`, `update(id, data)` |
| `productRepository.js` | Tabla `productos_servicios` | `findByDescription(desc)`, `create(data)`, `findAll()` |
| `auditRepository.js` | Tabla `auditoria_procesos` | `create(entry)`, `findByInvoiceId(id)`, `findByUser(userId)` |

**¿Por qué repositorios separados de servicios?**

Si mañana cambias de PostgreSQL a otro motor, solo reescribes los repositorios. Los servicios no se enteran. Además, los tests son mucho más fáciles: puedes simular (mockear) el repositorio sin necesitar una BD real.

---

### `src/middleware/` — Middleware de Express

El middleware son funciones que se ejecutan **antes** de que la petición llegue al controlador. Procesan, verifican o transforman la petición.

| Middleware | Qué hace | Cuándo se ejecuta |
|-----------|---------|-------------------|
| `authMiddleware.js` | Verifica que la petición incluya un token JWT válido. Si no lo tiene, devuelve 401 (no autorizado) | En todas las rutas protegidas. Sin token válido, no se accede a nada |
| `roleMiddleware.js` | Verifica que el usuario tenga el rol necesario para acceder a ese endpoint. Si no lo tiene, devuelve 403 (prohibido) | Después de `authMiddleware`. Comprueba permisos según rol: ADMIN, CONTABILIDAD, REVISOR, LECTURA |
| `errorHandler.js` | Captura cualquier error no controlado y devuelve una respuesta JSON con código de error apropiado. Registra el error en logs | Se registra al final de la cadena de middleware. Si algo falla en cualquier punto, este middleware lo recoge y responde de forma limpia en vez de que el servidor se caiga |
| `fileUpload.js` | Configura Multer para gestionar la subida de archivos. Define tamaño máximo (10MB), tipos permitidos (pdf, jpg, png), nombre seguro del fichero | Solo se activa en las rutas de subida de facturas. Valida que el archivo sea un tipo permitido y no supere el tamaño máximo |
| `requestLogger.js` | Registra en consola o archivo cada petición que llega: método, URL, IP, tiempo de respuesta, código de estado | Útil para depuración y monitorización. Permite saber qué está pasando en el servidor en todo momento |

---

### `src/validators/` — Validación de datos de entrada

Los validators comprueban que los datos que llegan del frontend tienen el **formato correcto** antes de procesarlos.

| Validator | Qué valida | Ejemplo |
|-----------|-----------|---------|
| `invoiceValidator.js` | Que los datos de factura sean correctos: número no vacío, fecha válida, importe numérico positivo, CIF con formato correcto | Si alguien envía un total de "-500€", se rechaza antes de llegar al service |
| `authValidator.js` | Que el email tenga formato válido, la contraseña tenga mínimo de caracteres, el rol sea uno de los permitidos | Previene datos basura en el registro/login |

**¿Por qué validators separados de middleware?**

El middleware gestiona cosas transversales (autenticación, logging, roles). Los validators son específicos de cada entidad y sus reglas de formato. Son conceptos distintos.

---

### `src/utils/` — Utilidades del backend

| Archivo | Qué contiene | Ejemplo |
|---------|-------------|---------|
| `helpers.js` | Funciones auxiliares genéricas | Generar IDs únicos, formatear fechas para PostgreSQL, calcular IVA, normalizar nombres de proveedores (quitar tildes, mayúsculas, eliminar S.L./S.A.) |
| `constants.js` | Constantes del sistema | Estados de factura (`SUBIDA`, `EN_PROCESO`, `PROCESADA_IA`, `PENDIENTE_REVISION`, `VALIDADA`, `RECHAZADA`, `SINCRONIZADA`, `ERROR_PROCESAMIENTO`), roles de usuario (`ADMIN`, `CONTABILIDAD`, `REVISOR`, `LECTURA`), tipos de IVA |
| `errors.js` | Clases de error personalizadas | `NotFoundError`, `ValidationError`, `UnauthorizedError`, `ForbiddenError`. Permite que el errorHandler sepa qué código HTTP devolver según el tipo de error |

---

### `src/database/migrations/` y `seeds/`

| Carpeta | Qué contiene | Por qué existe |
|---------|-------------|-----------------|
| `migrations/` | Scripts SQL versionados que modifican la estructura de la BD (crear tabla, añadir columna, etc.) | Permite evolucionar la BD de forma controlada. Cada migración se ejecuta una vez y en orden |
| `seeds/` | Scripts para insertar datos iniciales (usuario admin, tipos de IVA, datos de prueba) | Necesarios para que la app funcione desde el primer arranque |

---

## 5. Pipeline de procesamiento documental (Python)

> **Nota importante:** Esta sección se llama "pipeline de procesamiento documental" y no simplemente "IA" porque el procesamiento real de facturas combina múltiples técnicas: extracción de texto, OCR, reglas, expresiones regulares, plantillas y validación. La IA/ML es solo una parte del pipeline, no todo. La mayor parte del éxito viene de un buen preprocesado, reglas bien definidas y plantillas de proveedores conocidos.

```
ai-service/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── invoice_routes.py
│   │   └── health_routes.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ocr_service.py
│   │   ├── pdf_extractor.py
│   │   ├── invoice_classifier.py
│   │   ├── field_extractor.py
│   │   └── confidence_scorer.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── invoice_model.py
│   │   └── extraction_result.py
│   ├── templates/
│   │   └── .gitkeep
│   └── utils/
│       ├── __init__.py
│       ├── text_processing.py
│       ├── regex_patterns.py
│       └── image_processing.py
├── tests/
│   ├── __init__.py
│   ├── test_ocr_service.py
│   ├── test_field_extractor.py
│   └── test_invoice_classifier.py
├── requirements.txt
├── .env.example
└── Dockerfile
```

### ¿Por qué Python y no Node.js para el pipeline?

- **Tesseract/PaddleOCR**: las mejores librerías de OCR están en Python.
- **pdfplumber/PyMuPDF**: extracción de texto de PDFs mucho más madura en Python.
- **spaCy/transformers**: procesamiento de lenguaje natural solo existe de verdad en Python.
- **Regex avanzado**: Python tiene un módulo `re` más potente y cómodo.
- **Comunidad IA**: el 95% de ejemplos, tutoriales y modelos están en Python.
- **Preprocesamiento de imagen**: OpenCV, Pillow, scikit-image son nativos de Python.

Node.js es excelente para APIs, pero para procesamiento de documentos, Python es muy superior.

---

### Archivos raíz del servicio

| Archivo | Qué hace |
|---------|---------|
| `app/main.py` | Punto de entrada de FastAPI. Crea la aplicación, registra las rutas y configura CORS |
| `app/config.py` | Configuración del servicio: rutas de modelos, configuración de OCR, umbrales de confianza |
| `requirements.txt` | Lista de dependencias Python: fastapi, uvicorn, pdfplumber, pytesseract, Pillow, etc. |
| `.env.example` | Variables de entorno: rutas de Tesseract, configuración de OCR, umbrales |
| `Dockerfile` | Imagen Docker con Python, Tesseract OCR preinstalado y dependencias |

### Archivos `__init__.py`

**Qué son:** Archivos vacíos (o con imports) que le dicen a Python que esa carpeta es un paquete importable.

**Por qué existen:** Sin ellos, Python no puede hacer `from app.services.ocr_service import OcrService`. Es un requisito del lenguaje.

---

### `app/routes/` — Rutas del pipeline

| Archivo | Endpoints | Qué hace |
|---------|----------|---------|
| `invoice_routes.py` | `POST /extract` | Recibe un archivo PDF o imagen, lo procesa a través de todo el pipeline y devuelve el JSON con los datos extraídos |
| `health_routes.py` | `GET /health` | Devuelve si el servicio está activo y funcionando. Docker y el backend lo usan para saber si el pipeline está disponible antes de enviar facturas |

---

### `app/services/` — Pipeline de procesamiento

Esta es la parte técnica más importante del sistema. Cada servicio hace una tarea específica en la cadena de procesamiento. **No todo es "IA"**: gran parte del valor está en reglas, patrones y validación.

**Flujo del pipeline:**

```
Archivo recibido
      │
      ▼
┌─────────────────┐
│  pdf_extractor   │ ← Extrae texto de PDFs nativos (NO es IA, es lectura de PDF)
└────────┬────────┘
         │ (si no hay texto → es imagen escaneada)
         ▼
┌─────────────────┐
│   ocr_service    │ ← Convierte imagen a texto con OCR (modelo entrenado)
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  invoice_classifier  │ ← ¿Es factura de compra o de venta? (reglas + patrones)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   field_extractor    │ ← Extrae campos: nº, fecha, CIF, importes... (regex + plantillas + reglas)
└────────┬────────────┘
         │
         ▼
┌──────────────────────┐
│  confidence_scorer    │ ← ¿Cuánto confía el pipeline en lo que detectó? (validación + lógica)
└────────┬─────────────┘
         │
         ▼
    JSON resultado
```

| Servicio | Qué hace en detalle | Técnica principal | ¿Es "IA"? |
|----------|--------------------|--------------------|-----------|
| `pdf_extractor.py` | Abre el PDF y extrae el texto directamente si es un PDF con texto real (no escaneado). También extrae metadatos como número de páginas | Lectura de estructura PDF | No. Es parsing de archivos |
| `ocr_service.py` | Si el PDF es una imagen escaneada (sin texto seleccionable), convierte la imagen a texto usando reconocimiento óptico de caracteres | OCR (Tesseract/PaddleOCR) | Sí. Usa modelos entrenados |
| `invoice_classifier.py` | Analiza el texto extraído y determina si la factura es de compra o de venta. Busca patrones como el CIF de la empresa | Reglas + patrones | Parcialmente. Se puede mejorar con ML |
| `field_extractor.py` | Busca y extrae campos específicos: número de factura, fecha, CIF/NIF, base imponible, IVA, total, líneas de producto | Regex + plantillas + diccionarios | No principalmente. Es reglas y patrones |
| `confidence_scorer.py` | Calcula un porcentaje de confianza (0-100%) sobre la extracción. Evalúa: ¿se encontraron todos los campos?, ¿cuadra el IVA?, ¿las sumas son correctas? | Lógica de validación con pesos | No. Es validación matemática |

**¿Por qué `confidence_scorer` es importante?**

Es lo que permite que el sistema funcione con **dos modos**:

- **Confianza alta (≥90%) + proveedor conocido + sumas correctas**: se puede registrar automáticamente (modo automático, Fase 3).
- **Confianza media/baja (<90%)**: se muestra al usuario para revisión manual (modo asistido).

---

### `app/models/` — Modelos de datos (Pydantic)

| Modelo | Qué define | Por qué existe |
|--------|-----------|-----------------|
| `invoice_model.py` | Estructura de datos de una factura: campos obligatorios, tipos, valores por defecto | FastAPI usa modelos Pydantic para validar automáticamente las peticiones y respuestas. Si el JSON no cumple el modelo, FastAPI devuelve error 422 |
| `extraction_result.py` | Estructura del resultado de extracción: datos extraídos + confianza + campos que faltan + advertencias | Define exactamente qué devuelve el pipeline al backend. Es el **contrato** entre los dos servicios |

**Ejemplo de resultado de extracción:**

```json
{
  "tipo_factura": "compra",
  "numero_factura": "F-2026-0012",
  "fecha": "2026-03-10",
  "proveedor": "Proveedor SL",
  "cif_proveedor": "B12345678",
  "base_imponible": 1200.00,
  "iva": 252.00,
  "total": 1452.00,
  "lineas": [
    {
      "descripcion": "Licencias software",
      "cantidad": 2,
      "precio_unitario": 600.00
    }
  ],
  "confianza": 0.93,
  "campos_faltantes": [],
  "advertencias": ["El IVA detectado (21%) cuadra con la base imponible"]
}
```

---

### `app/templates/`

**Qué contiene:** Plantillas de facturas conocidas de proveedores frecuentes.

**Por qué existe:** Si un proveedor envía siempre facturas con el mismo formato, puedes crear una plantilla que diga "el número de factura está en la posición X, la fecha en la posición Y". Esto hace que la extracción sea mucho más precisa y rápida para proveedores recurrentes.

Es parte de la **Fase 1** de la estrategia: empezar con reglas fijas y plantillas antes de usar IA compleja.

---

### `app/utils/` — Utilidades de procesamiento

| Archivo | Qué hace | Ejemplo |
|---------|---------|---------|
| `text_processing.py` | Limpieza y normalización de texto: eliminar caracteres extraños, normalizar espacios, convertir a minúsculas para comparación | Un OCR puede devolver "F A C T U R A" en vez de "FACTURA". Este módulo lo normaliza |
| `regex_patterns.py` | Colección de expresiones regulares para detectar patrones en facturas españolas | Patrón para CIF: `[A-Z]\d{8}`, para fecha: `\d{2}/\d{2}/\d{4}`, para importe: `\d+[.,]\d{2}\s*€` |
| `image_processing.py` | Preprocesamiento de imágenes antes del OCR: rotar, ajustar contraste, binarizar, eliminar ruido | Una foto de factura puede estar torcida o con poca luz. Este procesamiento mejora mucho la precisión del OCR |

---

### `tests/` — Tests del pipeline

| Test | Qué prueba |
|------|-----------|
| `test_ocr_service.py` | Que el OCR extraiga texto correctamente de imágenes de ejemplo |
| `test_field_extractor.py` | Que los campos se extraigan correctamente de textos de prueba |
| `test_invoice_classifier.py` | Que la clasificación compra/venta funcione con ejemplos conocidos |

**¿Por qué tests aquí son prioritarios?**


El pipeline es el componente más crítico y más propenso a errores. Los tests verifican que los cambios en el código no rompan la extracción. Con cada proveedor nuevo o patrón nuevo, necesitas asegurarte de que no se rompen los anteriores.

---

## 6. Base de datos (PostgreSQL)

```
database/
├── init.sql
└── schema/
    ├── 001_create_tables.sql
    ├── 002_create_indexes.sql
    └── 003_seed_data.sql
```

| Archivo | Qué hace | Por qué existe |
|---------|---------|-----------------|
| `init.sql` | Script que se ejecuta al crear la BD por primera vez en Docker. Crea la base de datos y el usuario | Docker Compose ejecuta este archivo automáticamente cuando levanta el contenedor de PostgreSQL |
| `001_create_tables.sql` | Crea todas las tablas del sistema | Numerado con `001_` para que se ejecute en orden |
| `002_create_indexes.sql` | Crea índices para acelerar las consultas más frecuentes | Sin índices, buscar una factura por número en una tabla con 100.000 registros sería muy lento |
| `003_seed_data.sql` | Inserta datos iniciales: usuario administrador, tipos de IVA, estados | Para que la aplicación funcione desde el primer arranque |

### Tablas del sistema

| Tabla | Qué almacena | Columnas clave |
|-------|-------------|----------------|
| `usuarios` | Usuarios del sistema | id, email, password_hash, nombre, rol (`ADMIN` / `CONTABILIDAD` / `REVISOR` / `LECTURA`), activo, created_at |
| `facturas` | Facturas procesadas | id, numero_factura, tipo (`compra` / `venta`), fecha, proveedor_id, cliente_id, base_imponible, iva_porcentaje, iva_importe, total, estado, confianza_ia, validado_por (user_id), fecha_procesado, created_at, updated_at |
| `factura_lineas` | Líneas de detalle de cada factura | id, factura_id (FK), descripcion, cantidad, precio_unitario, subtotal, orden |
| `proveedores` | Proveedores detectados o registrados | id, nombre, nombre_normalizado, cif, direccion, email, telefono, created_at |
| `clientes` | Clientes de la empresa | id, nombre, nombre_normalizado, cif, direccion, email, telefono, created_at |
| `productos_servicios` | Catálogo de productos/servicios | id, descripcion, descripcion_normalizada, precio_referencia, categoria, created_at |
| `documentos_subidos` | Registro de archivos subidos | id, factura_id (FK), nombre_archivo, ruta_storage, tipo_mime, tamano_bytes, hash_archivo, fecha_subida |
| `processing_jobs` | **Estado del procesamiento de cada factura** | id, factura_id (FK), estado (`PENDIENTE` / `EN_PROCESO` / `COMPLETADO` / `ERROR`), started_at, finished_at, error_message, retry_count, worker_id |
| `auditoria_procesos` | Log de todas las acciones del sistema | id, usuario_id (FK), factura_id (FK), accion, detalle_json, ip_address, created_at |

### Estados de una factura

El ciclo de vida de una factura sigue estos estados, proporcionando **trazabilidad completa**:

```
SUBIDA → EN_PROCESO → PROCESADA_IA → PENDIENTE_REVISION → VALIDADA → SINCRONIZADA
                 │                                    │
                 └→ ERROR_PROCESAMIENTO               └→ RECHAZADA
```

| Estado | Significado | Quién lo activa |
|--------|-----------|-----------------|
| `SUBIDA` | La factura se ha subido al sistema pero aún no se ha enviado al pipeline | Sistema (automático al subir) |
| `EN_PROCESO` | El pipeline está procesando la factura | Sistema (cuando el pipeline empieza a trabajar) |
| `PROCESADA_IA` | El pipeline ha terminado y ha devuelto los datos extraídos | Sistema (al recibir respuesta del pipeline) |
| `PENDIENTE_REVISION` | Los datos están listos para que un usuario los revise | Sistema (automático tras procesamiento) |
| `VALIDADA` | Un usuario ha revisado y confirmado los datos | Usuario (al pulsar confirmar) |
| `RECHAZADA` | Un usuario ha descartado la factura (error, duplicada, ilegible...) | Usuario (al pulsar rechazar) |
| `SINCRONIZADA` | Los datos validados se han sincronizado con la BD de la empresa | Sistema (tras sincronización exitosa, Fase 2+) |
| `ERROR_PROCESAMIENTO` | Algo ha fallado durante el procesamiento del pipeline | Sistema (si el pipeline devuelve error) |

### Tabla `processing_jobs` — Por qué es importante

Esta tabla registra el **estado técnico** del procesamiento, independiente del estado de negocio de la factura:

- Si el pipeline tarda mucho, se puede detectar.
- Si falla, se puede saber **por qué** (`error_message`).
- Se puede **reintentar** automáticamente (`retry_count`).
- Se sabe **cuándo** empezó y terminó (`started_at`, `finished_at`).
- Se sabe **qué worker** lo procesó (útil si hay varios).

Esto es clave para monitorización y resolución de problemas.

### Columna `nombre_normalizado`

Las tablas `proveedores`, `clientes` y `productos_servicios` incluyen una columna `nombre_normalizado` que almacena el nombre procesado: sin tildes, en mayúsculas, sin "S.L.", "S.A.", etc. Esto permite hacer **búsquedas de matching difuso** de forma eficiente con una simple comparación de texto.

---

## 7. Integración con la BD empresarial

### Principio fundamental

> **Difactura nunca accede directamente a las tablas críticas del ERP o sistema contable de la empresa.** Toda la integración se realiza mediante una capa de sincronización controlada.

### ¿Por qué no conectar directamente?

- Las tablas del ERP pueden tener triggers, constraints y lógica que desconocemos.
- Escribir directamente puede romper integridad referencial.
- Puede generar duplicados si no se conoce el modelo exacto.
- Los flujos contables son delicados y están sujetos a normativa.
- Un error podría afectar a datos reales de la empresa.

### Cómo funciona la integración

```
┌─────────────┐         ┌──────────────────────┐         ┌──────────────┐
│ BD Difactura │────────▶│  Capa de sincroniz.  │────────▶│  BD Empresa  │
│  (tablas     │         │  (dbSyncService.js)  │         │  (ERP/Cont.) │
│   propias)   │◀────────│                      │◀────────│              │
└─────────────┘         └──────────────────────┘         └──────────────┘
```

**Difactura tiene sus propias tablas de trabajo** (facturas, proveedores, clientes, productos). Cuando una factura es validada, el `dbSyncService.js` se encarga de:

1. Comprobar si el proveedor ya existe en la BD empresarial (por CIF).
2. Comprobar si la factura ya está registrada (por número).
3. Preparar los datos en el formato que espera la BD empresarial.
4. Ejecutar la escritura dentro de una transacción.
5. Marcar la factura como `SINCRONIZADA` en Difactura.
6. Registrar la operación en auditoría.

Si algo falla, **la transacción se revierte** y la factura queda como `VALIDADA` (se puede reintentar).

### Evolución prevista

| Fase | Nivel de integración |
|------|---------------------|
| Fase 1 | Sin integración. Difactura es autónomo con BD propia |
| Fase 2 | Lectura de la BD empresarial para validar proveedores/clientes existentes |
| Fase 3 | Escritura controlada en BD empresarial para facturas con alta confianza y validación humana |

---

## 8. Seguridad

### Autenticación

| Mecanismo | Implementación | Detalle |
|-----------|---------------|---------|
| Contraseñas | Hashing con bcrypt (salt rounds: 12) | Las contraseñas nunca se almacenan en texto plano. Se aplica hash irreversible |
| Sesiones | JWT (JSON Web Tokens) | Token firmado con clave secreta, con expiración configurable (por defecto 8h). Se envía en header `Authorization: Bearer <token>` |
| Variables sensibles | Variables de entorno (.env) | Secretos como `JWT_SECRET`, `DATABASE_URL` nunca están en el código fuente. Se cargan desde archivos `.env` que están en `.gitignore` |

### Autorización (ver sección 9 para detalle de roles)

| Mecanismo | Implementación |
|-----------|---------------|
| Control de acceso por rol | `roleMiddleware.js` verifica el rol del usuario en cada endpoint protegido |
| Rutas protegidas en frontend | `ProtectedRoute.jsx` impide renderizar páginas si no hay sesión válida o rol adecuado |

### Validación de entrada

| Qué se valida | Dónde | Cómo |
|---------------|-------|------|
| Formato de datos (email, CIF, importes) | `validators/` | Funciones de validación antes de procesar |
| Ficheros subidos (tipo, tamaño) | `middleware/fileUpload.js` | Multer rechaza tipos no permitidos y archivos >10MB |
| Consultas SQL | `repositories/` | Consultas parametrizadas (`$1`, `$2`) que previenen inyección SQL |

### Protección de datos

| Aspecto | Cómo se protege |
|---------|-----------------|
| Datos en tránsito | HTTPS en producción (configurado en Nginx con certificado SSL/TLS) |
| Datos en reposo | PostgreSQL con autenticación obligatoria. Acceso solo por usuario/contraseña |
| Archivos de facturas | Almacenados fuera del directorio público. Acceso solo a través de la API con autenticación |
| Logs de auditoría | Inmutables (solo INSERT, nunca UPDATE ni DELETE). Incluyen usuario, IP y timestamp |

### Medidas adicionales

| Medida | Propósito |
|--------|----------|
| Rate limiting | Limita el número de peticiones por IP para prevenir ataques de fuerza bruta |
| CORS configurado | Solo acepta peticiones del dominio del frontend, no de cualquier origen |
| Helmet.js | Configura headers HTTP de seguridad (X-Content-Type-Options, X-Frame-Options, etc.) |
| Sanitización de nombres de archivo | Los archivos subidos se renombran con UUID para evitar path traversal |

---

## 9. Roles y permisos

### Roles del sistema

| Rol | Descripción | Usuarios típicos |
|----|-------------|-----------------|
| `ADMIN` | Acceso total al sistema. Puede crear usuarios, configurar ajustes, ver auditoría completa | Administrador del sistema, responsable IT |
| `CONTABILIDAD` | Puede subir, revisar, validar y rechazar facturas. Puede gestionar proveedores y clientes | Personal del departamento de contabilidad |
| `REVISOR` | Solo puede revisar y validar/rechazar facturas ya procesadas. No puede subir nuevas | Supervisores, jefes de departamento que solo validan |
| `LECTURA` | Solo puede ver el dashboard y el historial. No puede modificar nada | Gerencia, dirección, consultores externos |

### Matriz de permisos

| Acción | ADMIN | CONTABILIDAD | REVISOR | LECTURA |
|--------|-------|-------------|---------|---------|
| Ver dashboard | ✅ | ✅ | ✅ | ✅ |
| Ver historial de facturas | ✅ | ✅ | ✅ | ✅ |
| Subir facturas | ✅ | ✅ | ❌ | ❌ |
| Revisar datos detectados | ✅ | ✅ | ✅ | ❌ |
| Validar/confirmar factura | ✅ | ✅ | ✅ | ❌ |
| Rechazar factura | ✅ | ✅ | ✅ | ❌ |
| Editar datos de proveedor/cliente | ✅ | ✅ | ❌ | ❌ |
| Crear usuarios | ✅ | ❌ | ❌ | ❌ |
| Ver auditoría completa | ✅ | ❌ | ❌ | ❌ |
| Configuración del sistema | ✅ | ❌ | ❌ | ❌ |
| Forzar sincronización con BD empresa | ✅ | ❌ | ❌ | ❌ |

---

## 10. Nginx (Reverse Proxy)

```
nginx/
├── nginx.conf
└── Dockerfile
```

| Archivo | Qué hace | Por qué existe |
|---------|---------|-----------------|
| `nginx.conf` | Configuración del proxy inverso: redirige peticiones según la URL al servicio correcto. Configura SSL, compresión gzip y headers de seguridad | Sin Nginx, el usuario tendría que saber que el frontend está en un puerto, la API en otro y el pipeline en otro. Con Nginx, todo entra por el puerto 80/443 y se redirige automáticamente |
| `Dockerfile` | Imagen Docker de Nginx con la configuración personalizada | Para desplegarlo como contenedor |

**¿Qué es un reverse proxy?**

Es un servidor que recibe todas las peticiones y las reenvía al servicio correcto:

- `https://difactura.disoft.com/` → Frontend (build estática)
- `https://difactura.disoft.com/api/*` → Backend (Node.js)
- `https://difactura.disoft.com/ai/*` → Pipeline documental (Python)

El usuario solo ve una dirección. Internamente hay tres servicios.

**Solo se usa en producción.** En desarrollo, cada servicio corre en su puerto y Vite maneja el proxy hacia el backend.

---

## 11. Storage (Almacenamiento)

```
storage/
├── uploads/
│   └── .gitkeep
└── processed/
    └── .gitkeep
```

| Carpeta | Qué guarda | Por qué existe |
|---------|-----------|-----------------|
| `uploads/` | Facturas recién subidas por el usuario, pendientes de procesar | Cuando el usuario sube una factura, se guarda aquí temporalmente mientras el pipeline la procesa |
| `processed/` | Facturas ya procesadas y confirmadas | Una vez que la factura se procesa, se mueve aquí para archivo. Se mantiene el original por si hay que consultarlo |

**¿Por qué `.gitkeep`?**

Git no puede rastrear carpetas vacías. El archivo `.gitkeep` (vacío) sirve para que la carpeta se incluya en el repositorio. Cuando haya archivos reales, se ignorarán con `.gitignore`.

**Seguridad del almacenamiento:**

- Los archivos se renombran con UUID al subirlos (evita colisiones y path traversal).
- La carpeta `storage/` está fuera del directorio público del frontend.
- Solo se puede acceder a los archivos a través de la API con autenticación.
- Se almacena el hash SHA-256 del archivo en la tabla `documentos_subidos` para detectar duplicados.

---

## 12. Docker y entornos

### Archivos Docker

| Archivo | Dónde está | Qué hace |
|---------|-----------|---------|
| `docker-compose.yml` | Raíz del proyecto | Orquesta los 5 servicios (frontend, backend, ai-service, postgres, nginx). Con un solo comando (`docker-compose up`) levanta todo el sistema |
| `frontend/Dockerfile` | Frontend | **Producción:** compila con Vite y sirve con Nginx. **Desarrollo:** no se usa Docker, se ejecuta `npm run dev` |
| `backend/Dockerfile` | Backend | Construye la imagen del backend: instala dependencias, copia código, ejecuta con Node |
| `ai-service/Dockerfile` | Pipeline | Construye la imagen: instala Python, Tesseract OCR, dependencias pip, ejecuta con Uvicorn |
| `nginx/Dockerfile` | Nginx | Copia la configuración personalizada sobre la imagen base de Nginx. Solo producción |

### Diferencia entre desarrollo y producción

| Aspecto | Desarrollo | Producción |
|---------|-----------|------------|
| Frontend | `npm run dev` → Vite en puerto 5173 con hot reload | Build estática → servida por Nginx |
| Backend | `npm run dev` → nodemon con reinicio automático | `npm start` → Node.js detrás de Nginx |
| Pipeline | `uvicorn --reload` en puerto 8000 | `uvicorn` sin reload detrás de Nginx |
| BD | PostgreSQL local o en Docker | PostgreSQL en servidor dedicado o Docker |
| Proxy | No (Vite hace proxy en desarrollo) | Sí (Nginx enruta todo) |
| HTTPS | No | Sí (certificado SSL en Nginx) |

---

## 13. Monitorización y observabilidad

### Logs

| Servicio | Qué registra | Dónde |
|----------|-------------|-------|
| Backend | Cada petición HTTP (método, URL, IP, tiempo, código de respuesta) | Consola + archivo de log |
| Backend | Errores con stack trace completo | Consola + archivo de errores |
| Backend | Acciones de auditoría (subida, validación, sincronización) | Tabla `auditoria_procesos` |
| Pipeline | Tiempo de procesamiento de cada factura, errores de OCR | Consola + archivo de log |
| Nginx | Access log y error log de todas las peticiones | Archivos de log de Nginx |
| PostgreSQL | Queries lentas, errores de conexión | Log de PostgreSQL |

### Health checks

| Servicio | Endpoint | Qué verifica |
|----------|---------|--------------|
| Backend | `GET /api/health` | Que el servidor Node está activo y conectado a PostgreSQL |
| Pipeline | `GET /ai/health` | Que el servicio Python está activo y Tesseract funciona |

Docker Compose usa estos endpoints para saber si un servicio está sano. Si un health check falla, Docker puede reiniciar el contenedor automáticamente.

### Métricas básicas

El dashboard de la aplicación ya proporciona métricas de negocio:

- Facturas procesadas hoy/semana/mes.
- Tiempo medio de procesamiento.
- Tasa de éxito del pipeline.
- Facturas pendientes de revisión.
- Errores de procesamiento recientes.

### Evolución futura

Para un entorno de producción serio, se podría añadir:

- **Prometheus + Grafana** para métricas técnicas (CPU, memoria, latencia).
- **ELK Stack** (Elasticsearch + Logstash + Kibana) para centralizar logs.
- **Alertas** por email o Slack cuando hay errores críticos.

No es necesario para el MVP, pero el sistema está diseñado para que sea fácil de añadir.

---

## 14. Flujo completo de una factura

```
1. SUBIDA
   Usuario → React (UploadInvoice) → POST /api/invoices/upload → Node.js
   Estado: SUBIDA

2. REGISTRO
   Node.js → guarda PDF en storage/uploads/ → crea registro en BD
   Node.js → crea processing_job con estado PENDIENTE
   Estado: SUBIDA → EN_PROCESO

3. PROCESAMIENTO
   Node.js (aiClientService) → POST /ai/extract → Python (FastAPI)
   Pipeline: pdf_extractor → ocr_service → invoice_classifier
           → field_extractor → confidence_scorer
   Python → devuelve JSON con datos + confianza → Node.js
   processing_job: PENDIENTE → EN_PROCESO → COMPLETADO (o ERROR)
   Estado: EN_PROCESO → PROCESADA_IA (o ERROR_PROCESAMIENTO)

4. VALIDACIÓN AUTOMÁTICA
   Node.js (validationService): ¿cuadra el IVA? ¿CIF válido? ¿suma correcta?
   Node.js (supplierService): ¿proveedor existe? Matching por CIF o nombre normalizado
   Estado: PROCESADA_IA → PENDIENTE_REVISION

5. REVISIÓN HUMANA
   Node.js → devuelve datos al frontend → React (InvoiceReview)
   Usuario ve: datos detectados + documento original + nivel de confianza + advertencias
   El frontend consulta estado si sigue procesando (polling)

6. DECISIÓN DEL USUARIO
   a) Confirmar → PUT /api/invoices/:id/confirm → Estado: VALIDADA
   b) Rechazar → PUT /api/invoices/:id/reject → Estado: RECHAZADA

7. PERSISTENCIA
   Si validada:
   Node.js: actualiza datos en PostgreSQL (facturas, factura_lineas)
   Node.js: crea/actualiza proveedor si es nuevo (con nombre normalizado)
   Node.js: mueve PDF a storage/processed/
   Node.js: crea entrada en auditoria_procesos

8. SINCRONIZACIÓN (Fase 2+)
   Node.js (dbSyncService): sincroniza con BD empresarial
   Estado: VALIDADA → SINCRONIZADA

9. DASHBOARD
   React (Dashboard) → GET /api/dashboard/stats → Node.js → PostgreSQL
   Muestra: facturas del mes, compras vs ventas, proveedores top, pendientes de revisión
```

### Evolución: procesamiento asíncrono (Fase 3)

El flujo inicial es síncrono (Node espera a que Python termine). Para un sistema más robusto, el flujo evolucionaría a:

```
React sube factura → Node registra tarea en cola → Responde inmediatamente al usuario
                                                    ("tu factura se está procesando")
Cola (Redis + BullMQ) → toma la tarea → envía al pipeline de Python
Pipeline termina → actualiza processing_job → actualiza estado de factura
Frontend consulta estado periódicamente (polling) o recibe notificación (WebSocket)
```

**Ventajas del procesamiento asíncrono:**

- La petición HTTP no se queda colgada.
- El usuario puede seguir trabajando mientras se procesa.
- Se pueden procesar múltiples facturas en paralelo.
- Si el pipeline se cae, las tareas se reintentan automáticamente.

No es necesario para el MVP (Fase 1), pero la tabla `processing_jobs` ya está preparada para soportar este patrón.

---

## 15. Fases de implantación (Roadmap)

### Fase 1 — MVP básico funcional

**Objetivo:** Demostrar que el sistema funciona de punta a punta.

| Funcionalidad | Detalle |
|--------------|---------|
| Subida de facturas | PDF e imagen, drag & drop |
| Pipeline básico | Extracción de texto + OCR + reglas + regex |
| Clasificación | Compra vs venta por reglas simples |
| Extracción de campos | Número, fecha, CIF, importes, líneas |
| Revisión manual | Interfaz completa de revisión con preview del documento |
| Guardado en BD propia | Tablas de Difactura, sin tocar BD empresarial |
| Historial | Listado de facturas procesadas con filtros por estado |
| Login básico | Autenticación con JWT |

**Duración estimada:** 6-8 semanas.

---

### Fase 2 — Integración empresarial

**Objetivo:** Conectar con la BD real de la empresa y gestionar proveedores/clientes.

| Funcionalidad | Detalle |
|--------------|---------|
| Sincronización con BD empresa | Lectura para validar proveedores y clientes existentes. Escritura controlada de facturas validadas |
| Matching difuso | Detección de proveedores/clientes por CIF + nombre normalizado |
| Gestión de proveedores | CRUD completo, detección de duplicados |
| Dashboard completo | Métricas, gráficos, actividad reciente |
| Roles y permisos | ADMIN, CONTABILIDAD, REVISOR, LECTURA |
| Auditoría | Log completo de todas las acciones |

**Duración estimada:** 4-6 semanas adicionales.

---

### Fase 3 — Automatización y mejora continua

**Objetivo:** Reducir la intervención humana en facturas con alta confianza.

| Funcionalidad | Detalle |
|--------------|---------|
| Modo automático | Registro automático si: confianza ≥95%, proveedor conocido, sumas cuadran, CIF válido |
| Plantillas por proveedor | Plantillas predefinidas para proveedores frecuentes. Extracción mucho más precisa |
| Procesamiento por lotes | Subir múltiples facturas y procesarlas en cola (Redis + BullMQ) |
| Procesamiento asíncrono | Cola de tareas con reintentos automáticos |
| Aprendizaje con correcciones | Las correcciones humanas alimentan las reglas del pipeline. Cuanto más se usa, mejor extrae |
| Analítica avanzada | Tendencias de gasto, comparativa interanual, alertas de anomalías |
| Notificaciones | Email o WebSocket cuando una factura está lista para revisar |

**Duración estimada:** 6-8 semanas adicionales.

---

## 16. Riesgos y mitigaciones

| # | Riesgo | Impacto | Probabilidad | Mitigación |
|---|--------|---------|-------------|------------|
| 1 | **Facturas con formatos muy distintos** | Alto | Alta | Empezar con los 5-10 proveedores más frecuentes. Crear plantillas específicas. Ir ampliando con el uso |
| 2 | **PDFs que son imágenes escaneadas** | Medio | Alta | Pipeline con doble vía: extracción directa de texto + OCR como fallback. Preprocesamiento de imagen para mejorar calidad |
| 3 | **Errores de extracción** | Alto | Media | Nunca registrar automáticamente sin validación humana (Fase 1-2). Sistema de confianza con umbral. Revisión obligatoria por debajo del umbral |
| 4 | **Integridad de la BD empresarial** | Crítico | Baja | BD propia de Difactura separada. Capa de sincronización controlada. Transacciones con rollback. Nunca acceso directo |
| 5 | **Datos sensibles expuestos** | Crítico | Baja | HTTPS, JWT, bcrypt, consultas parametrizadas, archivos fuera de directorio público, logs de auditoría |
| 6 | **Pipeline se cae** | Medio | Media | Health checks, reinicio automático de Docker, tabla `processing_jobs` para reintentos. Las facturas quedan en cola, no se pierden |
| 7 | **Proveedores duplicados** | Medio | Alta | Matching por CIF (prioridad) + matching difuso por nombre normalizado. Revisión humana antes de crear nuevo proveedor |
| 8 | **Rendimiento con muchas facturas** | Medio | Baja (MVP) | Pool de conexiones PostgreSQL, índices en columnas clave, procesamiento asíncrono (Fase 3) |

---

## 17. Beneficios para la empresa

| Beneficio | Detalle |
|----------|---------|
| **Ahorro de tiempo** | De 5-10 minutos por factura manual a menos de 1 minuto con revisión asistida |
| **Reducción de errores** | La validación automática detecta inconsistencias que un humano puede pasar por alto (IVA mal calculado, CIF incorrecto) |
| **Trazabilidad completa** | Cada factura tiene un historial: quién la subió, cuándo se procesó, quién la validó, qué se cambió |
| **Detección de duplicados** | El sistema detecta si una factura ya fue procesada antes de registrarla |
| **Normalización de proveedores** | Evita tener el mismo proveedor con 3 nombres distintos en la BD |
| **Acceso desde cualquier sitio** | Al ser web, se puede acceder desde cualquier ordenador con navegador |
| **Escalabilidad** | Si el volumen de facturas crece, se pueden añadir recursos sin reescribir código |
| **Integración segura** | La capa de sincronización protege la BD empresarial de escrituras no controladas |

---

## 18. Resumen de tecnologías

| Capa | Tecnología | Versión recomendada | Para qué |
|------|-----------|-------------------|----------|
| Frontend | React | 18+ | Interfaz de usuario |
| Bundler | Vite | 5+ | Compilación y desarrollo |
| Estilos | Tailwind CSS | 3+ | Diseño visual |
| HTTP Client | Axios | 1+ | Llamadas al backend |
| Routing | React Router | 6+ | Navegación SPA |
| Backend | Node.js | 20 LTS | Servidor API |
| Framework API | Express | 4+ | Rutas y middleware |
| BD driver | pg (node-postgres) | 8+ | Conexión a PostgreSQL |
| Auth | jsonwebtoken + bcrypt | 9+ / 5+ | JWT y hashing |
| File Upload | Multer | 1+ | Gestión de archivos |
| Seguridad HTTP | Helmet.js | 7+ | Headers de seguridad |
| Pipeline | FastAPI | 0.100+ | API del servicio de procesamiento |
| OCR | Tesseract / PaddleOCR | 5+ / 2+ | Reconocimiento óptico de caracteres |
| PDF | pdfplumber / PyMuPDF | 0.10+ | Extracción de texto de PDF |
| NLP | spaCy (Fase 3) | 3+ | Procesamiento de lenguaje natural |
| Base de datos | PostgreSQL | 15+ | Persistencia |
| Contenedores | Docker + Docker Compose | 24+ | Despliegue |
| Proxy | Nginx | 1.25+ | Reverse proxy y SSL |
| Cola (Fase 3) | Redis + BullMQ | 7+ / 5+ | Procesamiento asíncrono |
