# Ejecutar un LLM local y gratis para estructurar texto

## Objetivo

Levantar el flujo `OCR/texto -> JSON` sin pagar APIs externas.

## Como funciona

- El OCR o extractor de texto obtiene el contenido de la factura
- Un modelo de texto local recibe ese contenido
- El modelo devuelve JSON estructurado
- `ai-service` valida y completa campos faltantes con el fallback heuristico
- No pagas inferencia a terceros

## Que necesitas

- Docker Desktop funcionando
- GPU NVIDIA opcional pero recomendable
- Espacio en disco para descargar el modelo local

## Configuracion

1. Copia [/.env.example](/c:/Users/raule/Documents/DISOFT/.env.example) a `.env` en la raiz.
2. Revisa estas variables:

```env
DOC_AI_ENABLED=true
DOC_AI_PROVIDER=ollama
DOC_AI_BASE_URL=http://ollama-service:11434
DOC_AI_MODEL=qwen2.5:3b
DOC_AI_TIMEOUT_SECONDS=600
DOC_AI_KEEP_ALIVE=1h
```

## Arranque del modelo

Primero levanta Ollama:

```bash
docker compose --profile doc-ai-text up -d ollama-service
```

Luego descarga el modelo una vez:

```bash
docker compose exec ollama-service ollama pull qwen2.5:3b
```

Y después arranca el servicio de IA y backend:

```bash
docker compose --profile doc-ai-text up -d ai-service backend
```

## Comprobaciones

Modelo local:

```bash
docker compose exec ollama-service ollama list
```

Servicio de IA:

```bash
docker compose --profile doc-ai-text logs -f ai-service
```

## Importante

- Esta configuracion esta pensada para local y sin coste de API
- El coste real es solo tu hardware y electricidad
- En una GTX 1650, este enfoque es bastante mas realista que un modelo visual grande
- `DOC_AI_KEEP_ALIVE=1h` ayuda a evitar arranques en frio si subes varias facturas seguidas
- Si `qwen2.5:3b` va lento, puedes probar `qwen2.5:1.5b`

## Siguiente paso

Cuando el modelo arranque, ya puedes enviar facturas al endpoint actual:

- `POST /ai/process`
- `POST /ai/extract`
