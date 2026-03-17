# Extraccion documental con IA

## Objetivo

Añadir un flujo `PDF/imagen -> JSON` en `ai-service` sin eliminar el pipeline actual.

## Enfoque

El servicio de IA ahora puede trabajar en modo hibrido:

- `heuristic`: OCR + reglas + clasificacion actual
- `openai_compatible`: intenta extraer con un modelo visual/documental y, si falla, vuelve al modo heuristico
- `ollama`: usa un modelo de texto local para convertir OCR/texto extraido a JSON y, si falla, vuelve al modo heuristico

## Flujo

1. Se sube un PDF o imagen.
2. `document_loader.py` obtiene:
   - texto extraido
   - numero de paginas
   - imagenes de las paginas
3. `document_intelligence.py`:
   - usa el proveedor configurado
   - fuerza salida JSON con un schema fijo
   - mezcla la respuesta del modelo con el fallback heuristico
4. El endpoint devuelve:
   - campos de factura
   - `provider`
   - `method`
   - `warnings`

## Variables de entorno

```env
DOC_AI_ENABLED=false
DOC_AI_PROVIDER=heuristic
DOC_AI_BASE_URL=http://ollama-service:11434
DOC_AI_API_KEY=
DOC_AI_MODEL=qwen2.5:3b
DOC_AI_TIMEOUT_SECONDS=120
DOC_AI_MAX_PAGES=4
DOC_AI_KEEP_ALIVE=1h
```

## Integracion prevista

La opcion `openai_compatible` esta pensada para servidores locales o internos que expongan una API compatible con `POST /chat/completions`, por ejemplo un servicio intermedio delante del modelo visual.

## Integracion local recomendada

El proyecto ya queda preparado para levantar dos tipos de proveedores locales con Docker Compose:

- texto a JSON:
  - servicio: `ollama-service`
  - perfil: `doc-ai-text`
  - modelo por defecto: `qwen2.5:3b`

- visual/documental:
  - servicio: `llm-service`
  - perfil: `doc-ai-vlm`
  - runtime: `vllm/vllm-openai`
  - modelo por defecto: `Qwen/Qwen2.5-VL-7B-Instruct`

Arranque:

```bash
docker compose --profile doc-ai-text up -d ollama-service ai-service backend
```

Configuracion minima para activar el flujo:

```env
DOC_AI_ENABLED=true
DOC_AI_PROVIDER=ollama
DOC_AI_BASE_URL=http://ollama-service:11434
DOC_AI_MODEL=qwen2.5:3b
```

Notas:

- `ollama` usa `format` con schema JSON para mejorar la consistencia de la respuesta
- `DOC_AI_KEEP_ALIVE=1h` reduce la probabilidad de que Ollama tenga que recargar el modelo entre facturas
- `openai_compatible` sigue disponible para un VLM grande si algun dia lo quieres en otra maquina
- la primera descarga del modelo ocupa varios GB

## Siguiente paso recomendado

Conectar un proveedor real y probarlo con 10-20 facturas:

- `Qwen2.5-VL-7B-Instruct` como primera prueba
- revisar JSON devuelto
- ajustar prompt y normalizacion
- medir latencia y consumo
