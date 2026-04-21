# Difactura

Aplicacion web para subir facturas en PDF o imagen, extraer sus datos automaticamente con IA Vision y revisarlos antes de validarlos.

## Que hace

- Sube facturas PDF o imagen desde la interfaz web (drag & drop o selector).
- Extrae datos estructurados con el motor visual (OpenAI Vision, gpt-5.4-mini).
- Muestra un panel de revision con todos los campos extraidos: emisor, receptor, importes, lineas de detalle.
- Permite editar y corregir campos antes de validar.
- Soporta IVA (peninsula) e IGIC (Canarias) incluyendo facturas con tipos impositivos mixtos.
- Guarda facturas, lineas de detalle y JSON de extraccion en PostgreSQL.
- Sistema multi-tenant por asesorias con roles de usuario.

## Stack

| Capa | Tecnologia |
|------|-----------|
| Frontend | React 18 + Vite 6 + Tailwind CSS |
| Backend | Node.js 20 + Express |
| Motor visual | FastAPI + OpenAI Vision (gpt-4.1-mini) |
| Base de datos | PostgreSQL 15 |
| Proxy de produccion | Nginx |
| Orquestacion | Docker Compose |

> El directorio `FAKEai-service-v2/` contiene un motor heuristico alternativo en estado experimental. **No forma parte del despliegue de produccion** y no debe levantarse en el entorno productivo.

## Arquitectura

```
frontend/            Interfaz React - revision y gestion de facturas
backend/             API REST, negocio y persistencia (Node.js/Express)
ai-service-vision/   Motor de extraccion IA Vision (puerto 8001)
FAKEai-service-v2/   Motor heuristico experimental - NO se despliega
database/            Esquema SQL y datos de prueba
docs/                Documentacion del proyecto
nginx/               Proxy inverso (perfil production)
storage/             Documentos originales subidos en runtime - no es codigo fuente
```

Flujo real de un documento:

1. El usuario sube un PDF o imagen desde el frontend.
2. El backend persiste el original en `storage/uploads/<uuid>.<ext>` y crea un job en PostgreSQL.
3. Un worker interno reclama el job (`FOR UPDATE SKIP LOCKED`) y lo envia a `ai-service-vision`.
4. El motor convierte el PDF a imagenes **en memoria**, llama a OpenAI Vision y devuelve el JSON estructurado.
5. El backend guarda el JSON en `facturas.documento_json` y deja la factura en revision.
6. El usuario revisa, corrige y valida o rechaza.

Las imagenes intermedias generadas por el motor IA **no se persisten**: se reconstruyen bajo demanda. El unico artefacto que vive fuera de PostgreSQL es el archivo original.

## Variables de entorno

La configuracion activa vive en `.env` en la raiz. El fichero esta en `.gitignore` y no se sube al repositorio.

Variables minimas necesarias:

```env
OPENAI_API_KEY=sk-...              # Obligatorio para el motor visual
JWT_SECRET=cambia_esto_en_prod     # Secreto JWT
POSTGRES_USER=difactura_user
POSTGRES_PASSWORD=...
POSTGRES_DB=difactura
DATABASE_URL=postgresql://difactura_user:...@db:5432/difactura
```

## Arranque rapido (desarrollo)

```bash
# Levantar base de datos, backend, frontend y motor visual
docker compose up db backend frontend ai-service-vision -d
```

Primera vez: la base de datos tarda ~15 segundos en estar `healthy`. El backend espera automaticamente.

Para reconstruir un servicio tras cambios en el Dockerfile:

```bash
docker compose up ai-service-vision --build -d --force-recreate
```

Para parar todo:

```bash
docker compose down
```

## Puertos

| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:3000/api/health |
| Motor visual | http://localhost:8001/health |
| Base de datos | localhost:5432 |

## Produccion

El `docker-compose.yml` que vive en la raiz esta orientado a **desarrollo** (bind mounts, `nodemon`, Vite dev server). No debe usarse tal cual en un servidor productivo.

El despliegue de produccion (Hetzner, dos nodos, HTTPS, backups, storage en volume persistente) esta documentado paso a paso en:

- [docs/produccion-hetzner.md](./docs/produccion-hetzner.md)

Ese documento contiene la auditoria del sistema, los bloqueantes a resolver antes del go-live, la estrategia de almacenamiento de documentos (Fase 1 volume Hetzner, Fase 2 object storage), las variables de entorno, el plan por fases y el runbook de puesta en marcha.

## Regimenes fiscales soportados

- **IVA** (peninsula): tipos habituales 4%, 10%, 21%
- **IGIC** (Canarias): tipos 0%, 3%, 7%, 15%
- Facturas con tipos mixtos: el desglose muestra cada base imponible y cuota por separado

El motor detecta el regimen automaticamente segun el emisor, los tipos impositivos encontrados y las palabras clave del documento.


## Estructura del proyecto

```
codigo vivo:     frontend/  backend/  ai-service-vision/  database/
documentacion:   docs/
runtime local:   storage/
experimental:    FAKEai-service-v2/  (no se despliega)
```

## Credenciales de demo

El seed incluye usuarios de prueba. Consulta `database/schema/003_seed_data.sql` para las credenciales iniciales.

## Flujo funcional

1. El usuario sube una factura.
2. El backend registra el documento y lanza el procesamiento.
3. `ai-service` extrae texto y estructura los campos.
4. La factura queda en revision.
5. El usuario puede corregir datos y lineas.
6. Finalmente valida o rechaza.

## Documentacion

- [Plan de produccion en Hetzner](./docs/produccion-hetzner.md) - auditoria, estrategia de almacenamiento, fases y runbook de despliegue.

