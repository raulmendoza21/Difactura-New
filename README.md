# Difactura

Aplicacion web para subir facturas en PDF o imagen, extraer sus datos automaticamente con IA Vision y revisarlos antes de validarlos.

## Que hace

- Sube facturas PDF o imagen desde la interfaz web (drag & drop o selector).
- Extrae datos estructurados con el motor visual (OpenAI Vision gpt-4.1-mini).
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
| Motor visual (activo) | FastAPI + OpenAI Vision (gpt-4.1-mini) |
| Motor heuristico (alternativo) | FastAPI + Mistral OCR + reglas + resolvedor |
| Base de datos | PostgreSQL 15 |
| Orquestacion | Docker Compose |

## Arquitectura

```
frontend/            Interfaz React — revision y gestion de facturas
backend/             API REST, negocio y persistencia (Node.js/Express)
ai-service-vision/   Motor de extraccion IA Vision — activo en produccion (puerto 8001)
ai-service-v2/       Motor documental heuristico — alternativa sin LLM (puerto 8000)
database/            Esquema SQL y datos de prueba
docs/                Documentacion del proyecto
nginx/               Proxy inverso (solo perfil production)
storage/             Documentos subidos en runtime — no es codigo fuente
models/              Cache de modelos locales — no se sube a Git
```

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
| Motor heuristico | http://localhost:8000/health |
| Base de datos | localhost:5432 |

## Produccion

```bash
docker compose --profile production up -d --build
```

Levanta nginx como proxy inverso ademas del resto de servicios.

## Regimenes fiscales soportados

- **IVA** (peninsula): tipos habituales 4%, 10%, 21%
- **IGIC** (Canarias): tipos 0%, 3%, 7%, 15%
- Facturas con tipos mixtos: el desglose muestra cada base imponible y cuota por separado

El motor detecta el regimen automaticamente segun el emisor, los tipos impositivos encontrados y las palabras clave del documento.

## Modelo de datos

| Tabla | Contenido |
|-------|-----------|
| `asesorias` | Asesorias fiscales (multi-tenant) |
| `usuarios` | Usuarios con roles: ADMIN, CONTABILIDAD, REVISOR, LECTURA |
| `clientes` | Empresas cliente de cada asesoria |
| `proveedores` | Emisores de facturas recibidas |
| `facturas` | Cabecera de cada factura (numero, fecha, importes, desglose de impuestos) |
| `factura_lineas` | Lineas de detalle (descripcion, cantidad, precio unitario, subtotal) |
| `documentos` | Fichero fisico y JSON completo de la extraccion |
| `auditoria` | Registro de cambios y validaciones |

## Estructura del proyecto

```
codigo vivo:     frontend/  backend/  ai-service-vision/  ai-service-v2/  database/
documentacion:   docs/
runtime local:   storage/  models/
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

- [Documento maestro del motor](./docs/motor-documental-desacoplado.md)
- [Contrato de datos documentales y contables](./docs/contrato-datos-documentales-y-contables.md)
- [API endpoints](./docs/api-endpoints.md)
- [Despliegue](./docs/deployment.md)

## Notas

- `samples/`, `storage/` y la cache de modelos no forman parte del repositorio.
- `artifacts/invoice-result-snapshots/` se usa solo para comparativas locales y snapshots temporales.
- El proyecto esta preparado para trabajar sin APIs de pago si usas `Ollama`.
- La primera factura puede tardar mas si el modelo local estaba en frio.
