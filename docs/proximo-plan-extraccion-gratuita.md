# Difactura - Proximo plan de extraccion gratuita

## 1. Objetivo de este documento

Este documento recoge el siguiente plan de trabajo para mejorar la calidad real de la extraccion documental sin coste de licencias o APIs externas.

La idea no es perseguir una solucion "magica", sino montar el mejor sistema posible a coste 0 dentro del proyecto actual.

---

## 2. Meta del siguiente ciclo

El siguiente objetivo no es todavia generar asientos contables reales.

La meta inmediata es esta:

- mejorar la captura de entrada
- mejorar OCR y estructuracion
- mejorar consistencia matematica y fiscal
- mejorar confianza y warnings
- dejar un JSON mucho mas fiable para una futura fase contable

---

## 3. Vision ideal gratuita para este proyecto

La mejor solucion posible a coste 0 no seria un unico modelo, sino un pipeline hibrido:

1. deteccion del tipo de documento
2. extraccion de texto segun el tipo de entrada
3. doble via de extraccion estructurada
4. fusion de resultados
5. reconciliacion matematica y fiscal
6. confianza por campo y warnings
7. revision humana guiada

Traducido al proyecto:

- `frontend/`
  - subida multiple
  - captura desde movil
  - revision editable
  - warnings claros
- `backend/`
  - jobs y estados
  - trazabilidad
  - orquestacion
- `ai-service/`
  - carga del documento
  - OCR / texto
  - extractor heuristico
  - extractor con Ollama
  - fusion de campos
  - reconciliacion fiscal y matematica
  - scoring de confianza

---

## 4. Principios que vamos a seguir

- no confiar en un solo motor de extraccion
- no confiar en una sola confianza global
- no mezclar "campo relleno" con "campo correcto"
- siempre preferir consistencia matematica y fiscal
- siempre dejar via de correccion humana
- aprovechar el historico del sistema cuando ya exista

---

## 5. Lineas de trabajo prioritarias

## 5.1. Captura de entrada

Antes de mejorar modelos, hay que mejorar la materia prima.

### Objetivo

Conseguir mejores documentos de entrada y menos OCR roto.

### Trabajo previsto

- detectar si el documento es PDF digital o imagen/foto
- si es PDF digital, priorizar extraccion de texto directa
- si es imagen/foto, pasar por OCR
- aplicar preprocesado minimo:
  - rotacion
  - recorte
  - contraste
  - limpieza basica

### Impacto esperado

- mejor OCR
- menos errores de proveedor, CIF y lineas
- menos necesidad de corregir manualmente

---

## 5.2. Captura directa desde camara en movil

Esto hay que implementarlo explicitamente.

### Objetivo

Que si la aplicacion se abre desde un movil, el usuario pueda sacar la foto de la factura directamente desde la web app.

### Que hay que hacer

- detectar si el dispositivo permite acceso a camara
- usar `navigator.mediaDevices.getUserMedia()` cuando compense
- mantener fallback con input file y `capture="environment"`
- permitir:
  - previsualizacion
  - repetir foto
  - confirmar foto
  - enviar la captura al mismo flujo de subida

### Requisitos UX

- pedir permisos de camara de forma clara
- mostrar mensaje si el navegador no soporta acceso directo
- no romper el flujo de escritorio
- dejar claro si la factura se esta enviando como foto unica o como parte de un lote

### Resultado esperado

- flujo real de "abrir en movil -> sacar foto -> enviar documento"
- mejor experiencia para facturas en papel

---

## 5.3. OCR / extraccion de texto

### Objetivo

Que el texto base sea lo mejor posible antes de estructurarlo.

### Trabajo previsto

- seguir aprovechando texto directo de PDF cuando exista
- mantener OCR actual como base
- evaluar mejora de OCR gratuito mas adelante:
  - mejor configuracion del OCR actual
  - alternativa gratuita tipo `PaddleOCR` o similar si compensa

### Criterio

No cambiar de OCR por cambiar.

Primero medir:

- donde falla mas
- en que tipo de documento
- si el problema es OCR o estructuracion

---

## 5.4. Doble via de extraccion

### Objetivo

No depender de una sola salida.

### Estrategia

Usar dos caminos:

- via heuristica / regex / reglas
- via Ollama / modelo local estructurador

Y luego comparar.

### Que hacer

- extraer por ambas vias
- fusionar por campo
- si coinciden, subir confianza
- si discrepan, bajar confianza y generar warning
- si una falla, usar la otra como fallback

### Campos donde mas compensa

- numero de factura
- fecha
- proveedor
- CIF
- subtotal / base
- impuesto
- total
- lineas

---

## 5.5. Fusion y reconciliacion

### Objetivo

Que el sistema no solo "lea", sino que compruebe.

### Reglas clave

- suma de lineas como candidata a base
- base + impuesto = total
- base * porcentaje = cuota
- inferencia de `IVA`, `IGIC`, `AIEM`, `EXEMPT`, `NOT_SUBJECT`
- validacion de CIF/NIF
- deteccion de posibles incoherencias por proveedor o cliente

### Resultado esperado

- menos casos con importes absurdos
- menos falsos positivos con confianza alta
- mejor `tax_breakdown`

---

## 5.6. Confianza por campo

### Objetivo

Que la confianza deje de ser solo un numero unico y pase a ser algo util.

### Evolucion deseada

Pasar de:

- confianza global

A:

- confianza por numero de factura
- confianza por fecha
- confianza por proveedor
- confianza por CIF
- confianza por subtotal
- confianza por impuesto
- confianza por total
- confianza por lineas

### Uso futuro

- resaltar en UI los campos dudosos
- ordenar revision humana por riesgo
- decidir cuando sugerir reproceso

---

## 5.7. Memoria del sistema y patrones

### Objetivo

Aprovechar conocimiento acumulado sin entrenar un modelo desde cero.

### Ideas a implementar despues

- proveedor conocido -> nombre canonicamente corregido
- proveedor conocido -> CIF preferente
- formato de factura ya visto -> reglas mas finas
- correcciones humanas repetidas -> heuristicas nuevas

### Importancia

Esto puede mejorar mucho la calidad real sin coste de IA adicional.

---

## 6. Orden recomendado de implementacion

## Fase A

- terminar mejoras de reconciliacion
- mejorar `tax_breakdown`
- mejorar `line_items`
- mejorar warnings de consistencia

## Fase B

- implementar confianza por campo
- exponer esos warnings y niveles en la revision

## Fase C

- implementar acceso a camara en movil
- unificar foto movil con el flujo de lotes

## Fase D

- mejorar OCR si los datos demuestran que sigue siendo el cuello de botella

## Fase E

- empezar a guardar memoria de proveedores y patrones

---

## 7. Trabajo concreto para manana

## 7.1. Extraccion

- revisar `tax_breakdown` y regimen fiscal
- mejorar deteccion de `IGIC` vs `IVA`
- mejorar propagacion de impuesto a lineas cuando aplique
- revisar identificacion de proveedor / cliente / CIF

## 7.2. Confianza

- definir que campos tendran confianza propia
- preparar estructura para devolver esa confianza
- decidir como se mostrara luego en revision

## 7.3. Camara movil

- revisar flujo actual de `UploadInvoice`
- definir componente o modulo para captura
- decidir si se hace con:
  - `getUserMedia`
  - o fallback directo por `input capture`
- implementar un primer flujo funcional en movil

## 7.4. Dataset de prueba

- seleccionar 10-20 facturas reales de prueba
- clasificar tipos:
  - PDF digital
  - escaneado
  - foto movil
  - factura simple
  - factura con varias lineas
  - factura con IGIC
  - factura con IVA
- usar siempre esas facturas para comparar mejoras

---

## 8. Criterio de exito del siguiente ciclo

Se considerara que este siguiente avance va bien si conseguimos:

- menos errores en base, impuesto y total
- mejor deteccion de regimen fiscal
- lineas mas fiables
- menor confianza cuando el documento no cuadra
- mejor experiencia de captura desde movil

---

## 9. Lo que todavia no toca

En este siguiente ciclo seguimos sin meternos en:

- generacion real de asientos contables
- integracion con base de datos contable real
- propuesta contable final
- sincronizacion con ERP

Primero hay que dejar el documento muy bien capturado y estructurado.

