# Produccion: Hosting, Arquitectura y Costes

Fecha: 2026-04-09

## Resumen

La opcion recomendada para este proyecto es:

- `nginx` + `frontend` compilado + `backend` Node + `ai-service` Python en **un servidor CPU**
- base de datos **externa de la empresa**: no incluida en este calculo
- almacenamiento de archivos en **Cloudflare R2**
- OCR principal en **Mistral OCR 3**
- LLM de apoyo `DOC_AI` en **Together AI**, de pago por uso

La idea es mantener el pipeline actual:

1. `Mistral OCR` como parser principal
2. reglas, heuristicas y validacion propias
3. `DOC_AI` solo cuando haga falta
4. salida final estructurada

## Opcion recomendada

### App server

- Proveedor: **Hetzner Cloud**
- Maquina recomendada: **CPX52**
- Capacidad: **16 vCPU / 32 GB RAM / 320 GB SSD**
- Precio oficial: **36,49 EUR/mes**

Esta maquina alojaria:

- `nginx`
- `frontend` compilado
- `backend` Node
- `ai-service` Python

## LLM de apoyo recomendado

Como el objetivo es que el LLM sea un servicio separado y de pago por uso, la opcion mas limpia es:

- Proveedor: **Together AI**
- Modelo recomendado para empezar: **`Qwen/Qwen3.5-9B`**
- Modelo alternativo mas fuerte: **`Qwen/Qwen3-235B-A22B-Instruct-2507-tput`**

Recomendacion practica:

- empezar con **`Qwen3.5-9B`**
- si se queda corto, subir a **`Qwen3-235B-A22B`**

## Diagrama del sistema

### Vista rapida

```text
                           +----------------------+
                           |       Usuario        |
                           | navegador / movil    |
                           +----------+-----------+
                                      |
                                      v
        +-------------------------------------------------------------+
        |                 Hetzner CPX52 (app server)                  |
        |                                                             |
        |  +-------------+     +------------------+                   |
        |  |    nginx    | --> | frontend static  |                   |
        |  | HTTPS/proxy | --> | build Vite       |                   |
        |  +------+------+     +------------------+                   |
        |         |                                                   |
        |         v                                                   |
        |  +------------------+        +---------------------------+   |
        |  |   backend Node   | <----> |     ai-service Python    |   |
        |  | auth, API, jobs  |        | OCR flow, heuristicas,   |   |
        |  | y negocio        |        | validacion, confianza    |   |
        |  +--------+---------+        +------+--------------------+   |
        +-----------|-------------------------|------------------------+
                    |                         |
                    |                         +-------------------------------+
                    |                                                        |
                    v                                                        v
     +----------------------------+                         +-----------------------------+
     | Base de datos empresa      |                         | Cloudflare R2               |
     | Postgres existente         |                         | originales y derivados      |
     +----------------------------+                         +-----------------------------+
                                                                      ^
                                                                      |
                                       +------------------------------+------------------+
                                       |                                                 |
                                       v                                                 v
                          +---------------------------+                     +---------------------------+
                          | Mistral OCR 3             |                     | Together AI DOC_AI        |
                          | parser principal OCR/PDF  |                     | fallback selectivo LLM    |
                          +---------------------------+                     +---------------------------+
```

### Flujo de una factura

```text
[1] Usuario sube factura
        |
        v
[2] nginx
        |
        v
[3] backend Node
        |
        +--> guarda archivo en R2
        |
        +--> registra job y llama a ai-service
                               |
                               v
                    [4] ai-service Python
                               |
                               +--> Mistral OCR 3
                               |
                               +--> reglas + heuristicas + validacion
                               |
                               +--> si hay duda -> Together DOC_AI
                               |
                               v
                    [5] JSON definitivo
                               |
                               v
                    [6] backend guarda resultado
                               |
                               v
                    [7] frontend muestra revision
```

## Reparto de responsabilidades

- `nginx`: HTTPS, proxy y entrega del frontend
- `backend`: autenticacion, usuarios, facturas, jobs y API principal
- `ai-service`: OCR orchestration, extraccion, resolucion semantica, confianza y fallback selectivo
- `Cloudflare R2`: almacenamiento de originales y derivados
- `Mistral OCR 3`: OCR/parser principal
- `Together AI`: LLM textual para ambiguedades o casos dudosos

## Fuentes oficiales de precios

- Hetzner Cloud: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- Cloudflare R2: https://developers.cloudflare.com/r2/pricing/
- Mistral OCR 3: https://docs.mistral.ai/models/ocr-3-25-12
- Together Serverless Models: https://docs.together.ai/docs/serverless-models

## Supuestos para estimar volumen

Para que los numeros sean comparables, estas tablas usan estos supuestos:

- la base de datos no se incluye
- media de **1,2 paginas por factura**
- media de **5 MB por factura** almacenada en R2
- `DOC_AI` entra solo en el **20%** de las facturas
- cuando entra `DOC_AI`, se envian aprox.:
  - **12.000 tokens de entrada**
  - **1.500 tokens de salida**
- para el calculo total orientativo se toma **EUR ~= USD**

## Precios unitarios usados

### Fijo

- Hetzner `CPX52`: **36,49 EUR/mes**

### Variables

- Mistral OCR 3:
  - **2 USD / 1000 paginas**
- Cloudflare R2 Standard:
  - **0,015 USD / GB-mes**
  - **10 GB gratis al mes**
  - para estos volumenes iniciales, las operaciones suelen quedar dentro del free tier
- Together `Qwen3.5-9B`:
  - **0,10 USD / 1M tokens de entrada**
  - **0,15 USD / 1M tokens de salida**
- Together `Qwen3-235B-A22B`:
  - **0,20 USD / 1M tokens de entrada**
  - **0,60 USD / 1M tokens de salida**

## Coste variable estimado por volumen

### Opcion recomendada: `Qwen3.5-9B`

| Volumen | OCR Mistral | DOC_AI Together | R2 primer mes | Variable total |
|---|---:|---:|---:|---:|
| 1.000 facturas/mes | 2,40 USD | 0,29 USD | 0,00 USD | 2,69 USD |
| 5.000 facturas/mes | 12,00 USD | 1,43 USD | 0,23 USD | 13,66 USD |
| 10.000 facturas/mes | 24,00 USD | 2,85 USD | 0,60 USD | 27,45 USD |

### Opcion mas fuerte: `Qwen3-235B-A22B`

| Volumen | OCR Mistral | DOC_AI Together | R2 primer mes | Variable total |
|---|---:|---:|---:|---:|
| 1.000 facturas/mes | 2,40 USD | 0,66 USD | 0,00 USD | 3,06 USD |
| 5.000 facturas/mes | 12,00 USD | 3,30 USD | 0,23 USD | 15,53 USD |
| 10.000 facturas/mes | 24,00 USD | 6,60 USD | 0,60 USD | 31,20 USD |

## Coste total mensual orientativo

Estos totales suman:

- servidor fijo Hetzner
- coste variable de OCR
- coste variable de `DOC_AI`
- almacenamiento R2 del primer mes

### Con `Qwen3.5-9B`

| Volumen | Fijo app server | Variable aprox | Total orientativo |
|---|---:|---:|---:|
| 1.000 facturas/mes | 36,49 EUR | ~2,69 | ~39-40 / mes |
| 5.000 facturas/mes | 36,49 EUR | ~13,66 | ~50-51 / mes |
| 10.000 facturas/mes | 36,49 EUR | ~27,45 | ~63-64 / mes |

### Con `Qwen3-235B-A22B`

| Volumen | Fijo app server | Variable aprox | Total orientativo |
|---|---:|---:|---:|
| 1.000 facturas/mes | 36,49 EUR | ~3,06 | ~39-40 / mes |
| 5.000 facturas/mes | 36,49 EUR | ~15,53 | ~52 / mes |
| 10.000 facturas/mes | 36,49 EUR | ~31,20 | ~67-68 / mes |

## Escenarios de coste separados

Para que quede claro, aqui van los escenarios separados sin mezclar conceptos.

### 1. Solo servidor de aplicacion

Incluye:

- `nginx`
- `frontend`
- `backend`
- `ai-service`

No incluye:

- base de datos
- OCR
- storage
- LLM

| Opcion | Infraestructura | Coste |
|---|---|---:|
| App server simple | Hetzner `CPX52` | **36,49 EUR/mes** |

### 2. Servidor de aplicacion + OCR + LLM de pago por uso

Incluye:

- Hetzner `CPX52`
- Mistral OCR 3
- Cloudflare R2
- Together `Qwen3.5-9B`

No incluye:

- base de datos

| Volumen | Hetzner | OCR + R2 + Together | Total |
|---|---:|---:|---:|
| 1.000 facturas/mes | 36,49 EUR | ~2,69 | ~39-40 / mes |
| 5.000 facturas/mes | 36,49 EUR | ~13,66 | ~50-51 / mes |
| 10.000 facturas/mes | 36,49 EUR | ~27,45 | ~63-64 / mes |

### 3. Servidor de aplicacion + OCR + LLM de pago por uso fuerte

Incluye:

- Hetzner `CPX52`
- Mistral OCR 3
- Cloudflare R2
- Together `Qwen3-235B-A22B`

| Volumen | Hetzner | OCR + R2 + Together | Total |
|---|---:|---:|---:|
| 1.000 facturas/mes | 36,49 EUR | ~3,06 | ~39-40 / mes |
| 5.000 facturas/mes | 36,49 EUR | ~15,53 | ~52 / mes |
| 10.000 facturas/mes | 36,49 EUR | ~31,20 | ~67-68 / mes |

### 4. Servidor de aplicacion + OCR + LLM self-hosted

Incluye:

- Hetzner `CPX52`
- Mistral OCR 3
- Cloudflare R2
- servidor GPU separado
- `Qwen2.5-32B-Instruct`

| Opcion | Comentario |
|---|---|
| Self-hosted 32B | descartada por ahora por coste fijo alto |

## Lectura practica

Lo mas importante de esta propuesta es esto:

- el coste fijo principal esta en el servidor de aplicacion
- el OCR de Mistral escala de forma bastante suave
- el `DOC_AI` selectivo, incluso con un modelo muy fuerte, no deberia dispararse demasiado si entra poco
- R2 apenas pesa al principio

## Recomendacion final

Si hoy hubiera que sacar este proyecto a produccion, la opcion mas sensata seria:

1. **Hetzner CPX52** para `nginx + frontend + backend + ai-service`
2. **Base de datos externa de la empresa**
3. **Cloudflare R2** para archivos
4. **Mistral OCR 3** como parser principal
5. **Together `Qwen3.5-9B`** como `DOC_AI` selectivo

Y solo si el fallback sigue quedandose corto:

6. subir `DOC_AI` a **`Qwen3-235B-A22B`**

Eso da una arquitectura limpia, comercializable y con un coste mensual bastante controlado.

## Conclusión clara

La opcion recomendada para este proyecto es:

- **Hetzner + R2 + Mistral + Together**

La opcion self-hosted de 32B se deja fuera por ahora porque mete un coste fijo demasiado alto para la fase actual del proyecto.
