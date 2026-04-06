# Difactura

Repositorio canonico de trabajo: `C:\Users\raule\Documents\DISOFT-NEW`

Si existe otra copia local como `DISOFT`, esta no es la referencia principal para el desarrollo actual.

Aplicacion web para subir facturas en PDF o imagen, extraer sus datos automaticamente y revisarlos antes de validarlos.

## Que hace

- Sube facturas desde una interfaz web.
- Procesa documentos con un servicio Python especializado.
- Estructura los datos extraidos a JSON.
- Permite revisar y editar los campos antes de validar.
- Guarda facturas, lineas, documentos y auditoria en PostgreSQL.
- Soporta una via complementaria local con `Ollama` para reforzar casos dudosos sin coste de API.

## Stack

- Frontend: React + Vite
- Backend: Node.js + Express
- Servicio documental: FastAPI + parser documental + resolvedor
- Base de datos: PostgreSQL
- Orquestacion local: Docker Compose
- Via complementaria local opcional: Ollama

## Arquitectura

- `frontend/`: interfaz de usuario
- `backend/`: API, negocio y persistencia
- `ai-service/`: extraccion documental y estructuracion
- `database/`: esquema y semillas
- `docs/`: documentacion del proyecto
- `models/`: cache local de modelos, no se sube a Git
- `storage/`: documentos runtime, no se sube a Git

## Estado actual del stack

Hoy el flujo principal de desarrollo funciona asi:

- `frontend` sirve la interfaz web
- `backend` orquesta negocio, jobs y persistencia
- `ai-service` es el motor documental principal
- `Mistral` actua como parser documental primario
- `ollama-service` se usa solo como apoyo selectivo de la via complementaria

Notas utiles:

- la configuracion activa vive en `/.env`
- `llm-service` existe como opcion futura, pero no forma parte del flujo normal actual
- `storage/` y `artifacts/` son salida local de trabajo, no codigo fuente

## Repo hygiene

Conviene entender estas carpetas asi:

- codigo vivo: `frontend/`, `backend/`, `ai-service/`, `database/`
- documentacion de trabajo: `docs/`
- runtime local: `storage/`, `models/`
- benchmarks y regresiones: `ai-service/benchmarks/`
- snapshots temporales: `artifacts/`

Regla practica:

- `storage/`, `models/` y `artifacts/` no son codigo fuente
- los benchmarks si forman parte del producto, porque protegen la generalizacion del motor
- la configuracion activa vive en `/.env`
- si `git status` muestra borrados en `artifacts/`, es normal hasta hacer el siguiente commit de limpieza

## Arranque rapido

1. Revisa y ajusta `/.env` en la raiz segun tu entorno antes de levantar el stack.
2. Levanta el stack de desarrollo actual:

```bash
docker compose --profile doc-ai-text up -d --build
```

3. Si es la primera vez y falta el modelo local, carga Ollama:

```bash
docker compose exec ollama-service ollama pull qwen2.5:3b
```

4. Para apagar todo:

```bash
docker compose --profile doc-ai-text down
```

5. Abre:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:3000/api/health`
- Motor documental: `http://localhost:8000/ai/health`

## Credenciales de desarrollo

Si recreas la base desde cero, puedes usar los usuarios demo del seed local o crear tus propios usuarios de desarrollo.

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
