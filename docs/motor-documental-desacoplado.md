# Difactura - Estrategia para un motor documental desacoplado

## 1. Objetivo

Este documento fija una decision de producto y arquitectura para la siguiente etapa del MVP:

- mantener el frontend actual
- mantener el backend actual como carcasa de negocio
- dejar de acoplar la evolucion del producto a la persistencia provisional del MVP
- construir un motor documental independiente, reutilizable y trasladable al producto final

La idea no es cerrar todavia la integracion con la base de datos real de cada empresa.
La prioridad ahora es conseguir un motor con la maxima robustez posible para leer:

- PDF digital
- PDF escaneado
- PDF que contiene una foto
- foto movil
- ticket o factura simplificada
- factura multipagina
- facturas con IGIC
- facturas con IRPF o retencion
- facturas rectificativas o importes negativos

---

## 2. Decision central

La app actual se va a tratar como un entorno de validacion del motor documental.

El objetivo de esta fase no es perfeccionar la persistencia definitiva, sino construir una pieza central estable:

- entrada generica: documento + contexto opcional de empresa
- salida generica: documento normalizado + evidencia + confianza + flags

Si el motor queda desacoplado de la base de datos provisional del MVP, luego se podra conectar a la base de datos real de cada empresa con mucho menos riesgo.

En otras palabras:

- el motor documental debe sobrevivir aunque cambie la base de datos final
- el frontend y el backend actuales pueden mantenerse
- lo que cambiara despues sera principalmente la capa de integracion y persistencia

---

## 3. Principios de diseno

El motor documental debe cumplir estos principios:

### 3.1 Agnostico de empresa

- no depender de nombres concretos de empresas en runtime
- no meter hardcodes de Disoft ni de ningun proveedor concreto
- usar el contexto de empresa solo como pista de desambiguacion

### 3.2 Agnostico de persistencia

- no depender de tablas concretas del MVP
- no mezclar OCR con logica de guardado final
- exponer un contrato de salida estable y portable

### 3.3 Layout-aware

- no basarse en texto plano como artefacto principal
- trabajar con paginas, bloques, spans, coordenadas y regiones
- usar evidencia por campo

### 3.4 Determinista donde sea posible

- usar reglas fuertes para matematicas, signos e impuestos
- no dejar que un LLM tome decisiones fiscales sin control
- preferir "no estoy seguro" antes que inventar datos

### 3.5 Escalable

- permitir cola y workers separados
- soportar miles de facturas al mes y varias asesorias a la vez
- permitir sustituir el proveedor OCR principal sin reescribir la app

---

## 4. Que se mantiene y que cambia

## 4.1 Se mantiene

- frontend actual de subida, revision y validacion
- backend actual como API de negocio
- estados de factura y jobs
- concepto funcional de empresa asociada y contraparte
- auditoria y trazabilidad
- revision humana como parte central del flujo

## 4.2 Cambia

- el motor de OCR y extraccion deja de estar casado con OCR local como camino principal
- el `ai-service` pasa a ser un motor documental desacoplado
- el backend deja de depender de la estructura interna del OCR y consume un contrato estable
- el almacenamiento final del MVP deja de ser una decision arquitectonica importante

---

## 5. Recomendacion tecnica principal

La recomendacion actual es esta:

### Motor primario

- OCR/document parser externo moderno como base
- opcion recomendada hoy: `Mistral OCR 2`

### Motor de interpretacion

- logica propia de Difactura
- resolucion de:
  - emisor
  - receptor
  - contraparte
  - compra o venta
  - IGIC
  - IRPF o retencion
  - rectificativas
  - lineas
  - coherencia matematica

### Fallback

- `Gemini Flash Lite` o `Gemini Flash`
- solo para documentos con baja confianza o conflicto fuerte
- nunca como fuente unica de verdad

### Revision humana

- obligatoria cuando el sistema no tenga evidencia suficiente

---

## 6. Por que esta opcion es la recomendada

No se recomienda seguir con `regex + OCR local + heuristicas` como nucleo principal para el producto final.

Motivos:

- regex no entiende layout
- OCR local gratuito puede ser digno, pero no suele igualar la robustez general de un parser documental comercial moderno
- al escalar a muchas asesorias, el problema deja de ser solo precision y pasa a ser tambien coste operativo, concurrencia y mantenimiento

Tampoco se recomienda usar un LLM multimodal generico como camino principal:

- puede ser muy barato
- pero es menos estable y menos determinista para contabilidad real

La estrategia mas equilibrada es:

- parser documental bueno y barato como base
- reglas propias como verdad de negocio
- fallback LLM barato solo para el long tail

---

## 7. Flujo objetivo del motor

```text
Usuario sube factura
  -> Backend crea documento y job
  -> Worker recoge el job
  -> Motor documental clasifica el input
  -> Motor documental llama al OCR principal
  -> OCR devuelve texto, estructura y geometria
  -> Difactura construye un document bundle interno
  -> Difactura resuelve campos y coherencia global
  -> Si la confianza es baja, llama al fallback
  -> Se genera JSON normalizado con evidencia y flags
  -> El backend lo guarda como resultado de extraccion
  -> La factura pasa a revision humana
```

### 7.1 Clasificacion de entrada

Antes de extraer, el motor debe decidir si trata:

- PDF digital
- PDF escaneado
- PDF con foto
- imagen o foto movil
- ticket o factura simplificada
- multipagina

### 7.2 Extraccion primaria

El OCR principal debe devolver, como minimo:

- texto por pagina
- bounding boxes
- bloques o spans
- tablas o estructura equivalente
- metadatos utiles para evidence

### 7.3 Bundle interno

Difactura debe convertir cualquier proveedor externo a un bundle propio con:

- `pages`
- `spans`
- `regions`
- `candidates`
- `raw_text`
- `input_profile`

### 7.4 Resolucion documental

Sobre ese bundle, el motor debe resolver:

- identidad del documento
- emisor y receptor
- empresa asociada contra documento
- contraparte real
- compra o venta
- base imponible
- impuestos
- retenciones
- total
- lineas
- tipo documental

### 7.5 Fallback selectivo

Solo si la confianza es insuficiente:

- mandar el documento o la pagina al fallback
- pedir solo los campos dudosos
- comparar el resultado con la salida principal
- tomar la mejor decision final o mandar a revision

---

## 8. Contrato estable del motor

La pieza clave para poder migrar despues al producto final es fijar una salida estable.

El motor debe devolver, como minimo:

- `normalized_document`
- `field_confidence`
- `coverage`
- `evidence`
- `decision_flags`
- `company_match`
- `processing_trace`
- `raw_text`
- `warnings`

Dentro de `normalized_document` deben existir al menos estos bloques:

- `document_meta`
- `classification`
- `identity`
- `issuer`
- `recipient`
- `totals`
- `tax_breakdown`
- `withholdings`
- `line_items`
- `payment_info`

Este contrato debe vivir por encima del MVP actual.
El backend actual puede adaptarlo a la estructura provisional.
El producto final podra adaptarlo luego a la base de datos real.

Relacion con documentacion ya existente:

- ver `docs/contrato-datos-documentales-y-contables.md`

---

## 9. Como encaja en la app actual

La estrategia recomendada no obliga a rehacer frontend ni backend.

## 9.1 Frontend

Se mantiene:

- subida
- revision
- validacion
- muestra de evidencias y warnings

No debe conocer detalles del proveedor OCR.
Solo debe consumir el resultado estandar del motor.

## 9.2 Backend

Se mantiene como:

- API de negocio
- gestor de jobs
- gestor de estados
- persistencia provisional del MVP
- capa de adaptacion entre el motor y la estructura actual

El backend no debe convertirse en el lugar donde viva la inteligencia documental principal.

## 9.3 AI service

Pasa a ser:

- un motor documental desacoplado
- con interfaz estable
- con proveedor OCR configurable
- con resolvedor propio de Difactura

---

## 10. Como deberia evolucionar el repo actual

## 10.1 Frontend

No requiere un rediseno principal.
Solo debe seguir consumiendo:

- datos extraidos
- evidencia
- flags
- confianza

## 10.2 Backend

Debe conservar:

- autenticacion
- gestion de empresas
- subida
- jobs
- revision
- auditoria

Debe evolucionar para que:

- la capa de procesamiento quede cada vez mas desacoplada del esquema provisional
- el guardado del resultado sea una adaptacion del contrato estandar

## 10.3 AI service

Debe refactorizarse hacia una arquitectura por capas:

- `provider client`
- `bundle builder`
- `candidate generators`
- `global resolver`
- `confidence scorer`
- `fallback resolver`

El cambio importante no es tirar todo lo que ya existe, sino cambiar el centro de gravedad:

- de OCR local como principal
- a proveedor externo como principal

---

## 11. Proveedor OCR principal y fallback

## 11.1 Recomendacion actual

Como decision actual de producto:

- primario: `Mistral OCR 2`
- fallback: `Gemini Flash Lite` o `Gemini Flash`

## 11.2 Motivo

Esta combinacion ofrece un equilibrio especialmente bueno entre:

- coste
- calidad documental
- velocidad
- escalabilidad
- facilidad para operar muchas facturas al mes

## 11.3 Coste orientativo

A fecha `2026-03-26`, segun documentacion oficial:

- `Mistral OCR 2`: `1 USD / 1000 pages`
- `Mistral OCR 2 annotated pages`: `3 USD / 1000 annotated pages`
- `Google Document AI Invoice Parser`: orden de `0.01 USD / pagina`
- `AWS Textract Analyze Expense`: orden de `0.01 USD / pagina`

Para Difactura, el OCR principal mas una capa propia suele ser mas rentable que delegar toda la interpretacion a un parser cerrado mas caro.

Estos precios pueden cambiar y deben verificarse antes de contratar.

Referencias oficiales:

- https://docs.mistral.ai/models/ocr-2-25-05
- https://docs.mistral.ai/capabilities/document_ai/basic_ocr
- https://cloud.google.com/vertex-ai/generative-ai/pricing
- https://cloud.google.com/document-ai/pricing
- https://aws.amazon.com/textract/pricing/

---

## 12. Despliegue objetivo en servidor

La topologia recomendada para cuando se quiera escalar de verdad es:

```text
Frontend
Backend API
Queue
Worker de extraccion
PostgreSQL
Object Storage
Proveedor OCR externo
Fallback LLM externo
```

### 12.1 Responsabilidades

Frontend:

- subida
- bandeja
- revision
- validacion

Backend API:

- auth
- empresa activa
- jobs
- auditoria
- persistencia temporal o final

Queue:

- desacoplar subida de procesamiento
- repartir carga
- permitir reintentos

Worker:

- coger documentos de la cola
- llamar al OCR principal
- resolver datos documentales
- llamar al fallback solo cuando haga falta

Object Storage:

- guardar originales
- servirlos a la UI y al worker

### 12.2 Escalado

El escalado importante no es el del frontend.
Es el de los workers.

Debe ser posible:

- tener varias asesorias subiendo a la vez
- procesar miles de facturas sin bloquear la web
- limitar la concurrencia por tenant o por empresa

---

## 13. Que no se debe cerrar todavia

En esta fase no hace falta cerrar:

- el esquema final de la base de datos de cada empresa
- la integracion con ERP real
- la forma final de persistir asientos contables

Lo que si debe quedar cerrado ahora es:

- la interfaz del motor
- el contrato del documento normalizado
- la logica de confianza
- la estrategia de evidence y review

---

## 14. Como se migrara al producto final

Cuando llegue el momento de conectarse a la base de datos real de una empresa, la idea es:

1. mantener el mismo motor documental
2. mantener el mismo contrato de salida
3. sustituir la capa de persistencia o integracion
4. mapear `normalized_document` al modelo real de la empresa

Es decir:

- no se rehace el motor
- no se rehace la UI de revision
- no se tiran las reglas de negocio
- se cambia la capa que adapta el resultado al sistema final

---

## 15. Criterios de exito de esta fase

La fase se considerara bien encaminada cuando:

- el motor procese bien familias documentales nuevas sin hardcodes por empresa
- la contraparte se resuelva de forma consistente
- compra y venta se detecten con alta fiabilidad
- los casos con baja confianza queden bien marcados
- el contrato del motor sea portable fuera del MVP actual
- la persistencia provisional deje de condicionar el diseno del motor

---

## 16. Siguiente paso recomendado

El siguiente paso practico no es integrar aun con la base de datos real.

El siguiente paso recomendado es:

1. definir formalmente el contrato del motor que se va a congelar
2. introducir una interfaz de proveedor OCR en `ai-service`
3. adaptar el bundle interno para aceptar un proveedor externo como principal
4. mantener el backend actual como cliente del motor
5. validar el nuevo motor contra benchmark y casos reales nuevos

Solo despues de eso tendra sentido hablar de migrar la persistencia al producto final.
