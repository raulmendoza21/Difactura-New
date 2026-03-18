# Extraccion documental con IA

## Estado de este documento

Este archivo queda como referencia tecnica del enfoque explorado en la etapa anterior del proyecto.

La vision actual del producto y la arquitectura objetivo deben tomarse de:

- `docs/estructura-proyecto.md`
- `docs/architecture.md`
- `docs/database-schema.md`
- `docs/deployment.md`

---

## Que se exploro en la fase previa

En la fase anterior se validaron estas ideas:

- separar OCR y estructuracion
- usar un servicio documental en Python
- probar una capa de estructuracion con IA sobre texto extraido
- mantener revision humana final

La conclusion mas importante fue:

- un modelo visual grande local no era realista para el hardware disponible
- un flujo OCR/texto + modelo pequeno/local para estructurar si era viable como experimento

---

## Aprendizajes reutilizables

Los aprendizajes que siguen siendo utiles para el rediseño son:

- OCR, interpretacion y logica contable deben desacoplarse
- la salida del modelo debe convertirse a estructura controlada
- siempre hacen falta normalizacion y validaciones posteriores
- la confianza del modelo no sustituye la validacion humana

---

## Papel de la IA en la nueva etapa

En la nueva vision del producto, la IA debe entenderse como una capacidad dentro del pipeline documental, no como el centro del sistema.

Su rol esperado es:

- ayudar a estructurar datos
- sugerir clasificacion y contexto
- apoyar la propuesta contable

Pero nunca:

- confirmar por si sola la contabilizacion final
- escribir directamente asientos sin supervision humana

---

## Decision vigente

La arquitectura nueva no parte de "montar mas IA", sino de construir un flujo serio:

1. recepcion
2. almacenamiento
3. cola de trabajos
4. OCR/extraccion
5. interpretacion asistida
6. propuesta contable
7. revision humana
8. validacion final

La IA queda subordinada a ese flujo.
