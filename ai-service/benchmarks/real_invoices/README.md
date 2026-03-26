# Real invoice benchmark

Este benchmark sirve para evitar regresiones al tocar la extracción.

## Qué contiene

- Un conjunto pequeño de facturas reales "golden".
- Un JSON con los campos mínimos esperados por factura.
- Un runner que reejecuta el pipeline actual y compara resultados.

## Cuándo usarlo

Úsalo siempre:

- antes de cambiar OCR, layout o heurísticas
- después de cambiar OCR, layout o heurísticas
- antes de dar por buena una mejora

## Regla de trabajo

Si una mejora arregla una factura nueva pero rompe una del benchmark, la mejora no se acepta todavía.

## Cómo ejecutarlo

Con el stack levantado y `ollama-service` disponible:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py
```

Para ejecutar un solo caso:

```powershell
docker compose exec -T ai-service python benchmarks/real_invoices/run_benchmark.py --case rectificativa_negative
```

## Cómo añadir una factura nueva

1. Copia el archivo original a `benchmarks/real_invoices/files/`
2. Añade su bloque esperado en `cases.json`
3. Ejecuta el runner
4. Si pasa y representa una familia nueva importante, ya forma parte de la red de seguridad

## Tickets / facturas simplificadas

En este momento el benchmark base incluye las familias más importantes ya probadas.
Los tickets se deben añadir en cuanto estén guardados también en el repo o en `storage/uploads`
para cubrir:

- ticket supermercado
- ticket restaurante / factura simplificada
- tickets con muchas líneas
- tickets con IGIC incluido
