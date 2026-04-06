# Real invoice benchmark

Este benchmark sirve para evitar regresiones al tocar la extraccion.

## Que contiene

- Un conjunto pequeno de facturas reales "golden"
- Un JSON con expectativas por caso
- Un runner que reejecuta el pipeline actual y compara resultados

## Cuando usarlo

Usalo siempre:

- antes de cambiar OCR, layout o heuristicas
- despues de cambiar OCR, layout o heuristicas
- antes de dar por buena una mejora

## Regla de trabajo

Si una mejora arregla una factura nueva pero rompe una del benchmark, la mejora no se acepta todavia.

## Como ejecutarlo

Con el stack levantado:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py
```

Para ejecutar un solo caso:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py --case rectificativa_negative
```

Para ejecutar una familia concreta:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py --family purchase_with_irpf
```

Para comparar rutas del motor:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py --route local_only --route mistral_primary
```

Rutas disponibles:

- `configured`
- `local_only`
- `mistral_primary`
- `mistral_only`

El resumen muestra:

- resultado por caso
- resumen por familia
- resumen por campo
- proveedor y fallback observados por caso

Opcionalmente se puede guardar un JSON:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py --route local_only --json-out /tmp/benchmark-local.json
```

## Como anadir una factura nueva

1. Copia el archivo original a `benchmarks/real_invoices/files/`
2. Anade su bloque esperado en `cases.json`
3. Asigna una `family` documental generica
4. Ejecuta el runner
5. Si pasa y representa una familia nueva importante, ya forma parte de la red de seguridad

## Objetivo de esta fase

El benchmark no debe limitarse a "6/6 OK". Debe servir para:

- medir por campo
- medir por familia
- comparar rutas del motor
- detectar si una mejora arregla una cosa rompiendo otra
