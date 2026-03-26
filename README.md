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
- Soporta un flujo local con modelo `ollama` para estructuracion sin coste de API.

## Stack

- Frontend: React + Vite
- Backend: Node.js + Express
- Servicio documental: FastAPI + OCR + capa de extraccion
- Base de datos: PostgreSQL
- Orquestacion local: Docker Compose
- IA local opcional: Ollama

## Arquitectura

- `frontend/`: interfaz de usuario
- `backend/`: API, negocio y persistencia
- `ai-service/`: extraccion documental y estructuracion
- `database/`: esquema y semillas
- `docs/`: documentacion tecnica
- `models/`: cache local de modelos, no se sube a Git
- `storage/`: documentos runtime, no se sube a Git

## Arranque rapido

1. Copia `/.env.example` a `.env` en la raiz si vas a usar el proveedor local de IA.
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
- AI service: `http://localhost:8000/ai/health`

## Credenciales de desarrollo

Con la semilla actual:

- Email: `admin@difactura.local`
- Password: `Admin123!`

## Flujo funcional

1. El usuario sube una factura.
2. El backend registra el documento y lanza el procesamiento.
3. `ai-service` extrae texto y estructura los campos.
4. La factura queda en revision.
5. El usuario puede corregir datos y lineas.
6. Finalmente valida o rechaza.

## Documentacion

- [Estructura del proyecto](./docs/estructura-proyecto.md)
- [Extraccion documental con IA](./docs/ia-document-extraction.md)
- [LLM local gratis](./docs/local-llm-gratis.md)
- [Entorno Python](./docs/python-env.md)
- [Esquema de base de datos](./docs/database-schema.md)
- [Despliegue](./docs/deployment.md)

## Notas

- `samples/`, `storage/` y la cache de modelos no forman parte del repositorio.
- El proyecto esta preparado para trabajar sin APIs de pago si usas `ollama`.
- La primera factura puede tardar mas si el modelo local estaba en frio.
