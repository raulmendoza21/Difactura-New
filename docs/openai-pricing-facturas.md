# OpenAI API — Precios y arquitecturas para extracción de facturas

> Fecha: 10 abril 2026 | Precios oficiales de https://developers.openai.com/api/docs/pricing

---

## 1. Precios por modelo (por 1M tokens)

| Modelo | Input | Input cacheado | Output | Nivel |
|---|---|---|---|---|
| **gpt-4.1-nano** | $0.10 | $0.025 | $0.40 | Bueno, ultra-barato |
| **gpt-4.1-mini** | $0.40 | $0.10 | $1.60 | Muy bueno |
| **gpt-4.1** | $2.00 | $0.50 | $8.00 | Excelente |
| **gpt-5.4-nano** | $0.20 | $0.02 | $1.25 | Bueno (nueva gen) |
| **gpt-5.4-mini** | $0.75 | $0.075 | $4.50 | Muy bueno (nueva gen) |
| **gpt-5.4** | $2.50 | $0.25 | $15.00 | Máximo |

### Descuentos disponibles
- **Batch API**: -50% en input y output (procesamiento async, hasta 24h)
- **Cached input**: -75% a -90% si el prompt del sistema se repite (automático)
- **Flex processing**: precios reducidos para respuestas no urgentes

---

## 2. Tokens por factura (estimación)

### Modo texto (OCR ya hecho → solo LLM)
- **Input**: ~1,500 tokens (prompt sistema + texto OCR + contexto empresa)
- **Output**: ~200 tokens (JSON con campos extraídos)
- Con cached input (prompt sistema repetido): ~500 tokens nuevos + ~1,000 cacheados

### Modo visión (imagen directa al modelo)
- **Input imagen**: ~1,500-4,000 tokens (según resolución, detail=high)
- **Input texto**: ~500 tokens (prompt + instrucciones)
- **Output**: ~300 tokens (JSON completo, sin heurísticas previas)
- Factura típica A4 (~1800x2400px): ~1,452 patches × multiplicador modelo

---

## 3. Coste por factura

### A) Solo texto (reemplazar Ollama por OpenAI)

| Modelo | Coste/factura | Con cache | Con Batch+cache |
|---|---|---|---|
| gpt-4.1-nano | **$0.00023** | $0.00014 | $0.00007 |
| gpt-4.1-mini | **$0.00092** | $0.00055 | $0.00028 |
| gpt-4.1 | **$0.00460** | $0.00275 | $0.00138 |
| gpt-5.4-nano | **$0.00055** | $0.00030 | $0.00015 |
| gpt-5.4-mini | **$0.00203** | $0.00113 | $0.00056 |
| gpt-5.4 | **$0.00675** | $0.00363 | $0.00181 |

> Cálculo: 1,500 tok input × precio_input + 200 tok output × precio_output  
> Cache: 1,000 tok cacheado + 500 tok nuevo  
> Para esta opción hay que sumar el coste de Mistral OCR (~$0.001/página)

### B) Visión directa (imagen → OpenAI, sin Mistral OCR)

| Modelo | Coste/factura | Con Batch |
|---|---|---|
| gpt-4.1-nano | **$0.00060** | $0.00030 |
| gpt-4.1-mini | **$0.00240** | $0.00120 |
| gpt-4.1 | **$0.01200** | $0.00600 |
| gpt-5.4-nano | **$0.00125** | $0.00063 |
| gpt-5.4-mini | **$0.00488** | $0.00244 |
| gpt-5.4 | **$0.01625** | $0.00813 |

> Cálculo: ~4,000 tok imagen + 500 tok prompt + 300 tok output  
> Sin coste adicional de Mistral OCR

### C) Coste total real por factura (pipeline completo)

| Arquitectura | Modelo | Coste total/factura |
|---|---|---|
| Mistral OCR + gpt-4.1-nano | texto | **~$0.0012** |
| Mistral OCR + gpt-4.1-mini | texto | **~$0.0019** |
| Mistral OCR + gpt-5.4-nano | texto | **~$0.0016** |
| Solo gpt-4.1-nano visión | imagen | **~$0.0006** |
| Solo gpt-4.1-mini visión | imagen | **~$0.0024** |
| Solo gpt-5.4-nano visión | imagen | **~$0.0013** |
| Solo gpt-5.4 visión | imagen | **~$0.0163** |
| **Actual (Mistral OCR + Ollama local)** | — | **~$0.001** (solo Mistral) |

---

## 4. Coste mensual por volumen

### Opción A: Mistral OCR + OpenAI texto (como ahora pero mejor modelo)

| Facturas/mes | gpt-4.1-nano | gpt-4.1-mini | gpt-5.4-nano | gpt-5.4-mini |
|---|---|---|---|---|
| **50** | $0.06 | $0.10 | $0.08 | $0.15 |
| **100** | $0.12 | $0.19 | $0.16 | $0.30 |
| **200** | $0.24 | $0.38 | $0.32 | $0.60 |
| **500** | $0.60 | $0.95 | $0.80 | $1.50 |
| **1,000** | $1.20 | $1.90 | $1.60 | $3.00 |
| **5,000** | $6.00 | $9.50 | $8.00 | $15.00 |

### Opción B: Solo OpenAI visión (sin Mistral, imagen directa)

| Facturas/mes | gpt-4.1-nano | gpt-4.1-mini | gpt-5.4-nano | gpt-5.4 |
|---|---|---|---|---|
| **50** | $0.03 | $0.12 | $0.06 | $0.81 |
| **100** | $0.06 | $0.24 | $0.13 | $1.63 |
| **200** | $0.12 | $0.48 | $0.25 | $3.25 |
| **500** | $0.30 | $1.20 | $0.63 | $8.13 |
| **1,000** | $0.60 | $2.40 | $1.25 | $16.25 |
| **5,000** | $3.00 | $12.00 | $6.25 | $81.25 |

### Opción C: Batch API (procesamiento async, -50%)

| Facturas/mes | gpt-4.1-nano visión | gpt-5.4-nano visión | gpt-5.4 visión |
|---|---|---|---|
| **50** | $0.02 | $0.03 | $0.41 |
| **100** | $0.03 | $0.06 | $0.81 |
| **500** | $0.15 | $0.31 | $4.06 |
| **1,000** | $0.30 | $0.63 | $8.13 |
| **5,000** | $1.50 | $3.13 | $40.63 |

---

## 5. Comparativa de arquitecturas

### Opción A — Cambio mínimo (implementado, 5 min)
```
[PDF/imagen] → Mistral OCR → Texto → Heurísticas/Regex → OpenAI rellena débiles → JSON
```
- **Cambio**: 3 variables en `.env`
- **Estado**: ✅ YA CONFIGURADO con gpt-4.1-nano
- **Pro**: Sin tocar código, pipeline probado, heurísticas como primera línea
- **Con**: Doble coste (Mistral + OpenAI), calidad limitada por heurísticas

### Opción B — Visión directa (1-2 días desarrollo)
```
[Imagen/PDF] → OpenAI Vision → JSON completo (OCR + extracción en 1 llamada)
```
- **Cambio**: Nuevo provider `openai_vision_parser.py`
- **Pro**: Elimina Mistral (~$0.001/pág ahorro), pipeline más simple, potencialmente mejor
- **Con**: Sin fallback heurístico, dependencia total OpenAI

### Opción C — Doble pasada (máxima calidad)
```
[Imagen] → Mistral OCR → Heurísticas → OpenAI Vision valida/corrige → JSON final
```
- **Cambio**: Añadir paso de validación con visión
- **Pro**: Máxima precisión, dos capas independientes verifican
- **Con**: Coste doble (Mistral + OpenAI visión), más lento

### Opción D — Visión + Validación humana (producto profesional)
```
[Imagen] → OpenAI Vision → Auto-aprobado si confianza > 0.90
                          → Cola revisión humana si < 0.90
                          → Correcciones = datos para mejorar prompts
```
- **Pro**: Máxima calidad con safety net, escalable
- **Con**: Requiere UI de validación (parcialmente existe en frontend)

---

## 6. Resumen ejecutivo

| | Actual | Opción A (hoy) | Opción B (futuro) |
|---|---|---|---|
| **OCR** | Mistral API | Mistral API | OpenAI Vision |
| **Extracción** | Heurísticas + Ollama local | Heurísticas + OpenAI | OpenAI directo |
| **Coste 100 fact/mes** | ~$0.10 | ~$0.12 | ~$0.06 |
| **Coste 1000 fact/mes** | ~$1.00 | ~$1.20 | ~$0.60 |
| **GPU necesaria** | Sí (Ollama) | No | No |
| **Calidad esperada** | Media-Alta | Alta | Muy Alta |
| **Latencia** | ~12s | ~3s | ~2s |
| **Cambio necesario** | — | 3 vars .env | Nuevo provider |

> **Conclusión**: Con gpt-4.1-nano, incluso procesando 5,000 facturas al mes el coste es ~$3-6. 
> La GPU de Ollama cuesta más en electricidad que toda la API de OpenAI combinada.
