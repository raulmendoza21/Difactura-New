# Uso de LLM local gratis

## Estado de este documento

Este documento ya no define la direccion del proyecto. Queda como nota tecnica de una exploracion previa para ejecutar inferencia local sin coste de API.

La documentacion principal del nuevo enfoque esta en:

- `docs/estructura-proyecto.md`
- `docs/architecture.md`
- `docs/deployment.md`

---

## Que se valido

En la etapa anterior se comprobo que era posible:

- usar un modelo local pequeno para estructurar texto OCR a JSON
- integrar esa inferencia local con el servicio documental
- mantener el coste de API en cero

---

## Que limite aparecio

El principal limite no fue de integracion, sino de operativa:

- hardware local limitado
- calentamiento del modelo
- latencia variable
- mantenimiento de GPU y entorno de inferencia

---

## Como debe leerse ahora

Este documento debe entenderse solo como:

- referencia de un spike tecnico previo
- prueba de viabilidad de inferencia local
- antecedente util para futuras decisiones

No debe tomarse como la arquitectura objetivo del nuevo producto.
