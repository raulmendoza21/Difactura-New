# Difactura - Plan de implementacion del MVP documental

## 1. Objetivo del plan

Este documento convierte la vision del proyecto en un plan de ejecucion realista.

El foco de esta primera etapa es muy concreto:

- recibir documentos de facturas de forma comoda
- procesarlos en segundo plano
- extraer datos utiles con buena calidad
- permitir revision humana clara y rapida

La capa contable, los asientos, las contrapartidas y las integraciones externas quedan fuera de este primer ciclo.

---

## 2. Decisiones ya fijadas

Estas decisiones se consideran cerradas para arrancar:

- el MVP es solo para usuarios internos de asesoria
- el sistema debe soportar subida multiple de PDF e imagen
- la captura desde movil debe estar contemplada desde el inicio a nivel de UX responsive
- la subida no debe bloquearse esperando a que termine el OCR o la IA
- el procesamiento debe ser asincrono y basado en jobs
- la validacion final siempre la hace un humano
- la contabilidad se pospone a una segunda fase

---

## 3. Resultado que debe conseguir el MVP

Se considerara que el MVP ya funciona cuando una asesoria pueda:

1. iniciar sesion
2. elegir una empresa cliente
3. subir varias facturas seguidas
4. ver que los documentos entran en cola y cambian de estado
5. revisar el resultado automatico de cada factura
6. corregir campos clave si hace falta
7. aceptar, rechazar o reprocesar
8. mantener trazabilidad basica del proceso

---

## 4. Enfoque de implementacion

No vamos a rehacer todo el producto de golpe.

La estrategia recomendada es construir el nuevo MVP como una serie de cortes verticales pequenos, manteniendo de forma temporal las piezas reutilizables del proyecto actual:

- `frontend/` como base de la web app
- `backend/` como API de negocio y orquestacion
- `ai-service/` como motor de extraccion reutilizable
- `database/` para redefinir el esquema minimo de esta fase

La prioridad no es tener la arquitectura final perfecta desde el dia uno, sino conseguir un flujo documental robusto sobre una base que luego pueda evolucionar.

---

## 5. Orden de construccion

## Hito 0 - Base y limpieza de alcance

Objetivo:
dejar el repo listo para construir el MVP documental sin arrastrar decisiones de la fase anterior.

Entregables:

- documentacion alineada con el nuevo MVP
- decision de que modulos actuales se reutilizan temporalmente
- listado de funcionalidades que se congelan hasta fase 2
- nomenclatura comun de estados del documento y del job

Definicion de terminado:

- el equipo tiene claro que el primer corte no incluye contabilidad
- existe un vocabulario unico para documentos, jobs y revision

## Hito 1 - Contexto de asesoria y empresa cliente

Objetivo:
tener el marco funcional minimo para operar como asesoria.

Documento de detalle:

- ver `docs/hito-1-contexto-asesoria.md`

Entregables:

- login de usuario interno de asesoria
- contexto persistente de asesoria autenticada
- listado y seleccion de empresa cliente
- permisos basicos por rol interno si hacen falta

Dependencias:

- modelo minimo de `Asesoria`, `Usuario` y `EmpresaCliente`

Definicion de terminado:

- un usuario autenticado solo ve empresas cliente de su asesoria
- la seleccion de empresa queda disponible para la subida y la bandeja

## Hito 2 - Recepcion y almacenamiento de documentos

Objetivo:
resolver bien la entrada documental antes de procesar.

Entregables:

- subida multiple de PDF e imagen
- validacion de formatos y tamano
- asociacion del lote al usuario y empresa cliente
- almacenamiento del archivo original con `storage_key`
- generacion de hash y metadatos tecnicos

Decisiones tecnicas de esta fase:

- para el MVP, guardar archivos fuera de la base principal y almacenar en BD solo la referencia
- usar almacenamiento local en desarrollo y dejar una interfaz preparada para object storage

Definicion de terminado:

- subir un lote de documentos devuelve respuesta rapida
- cada documento queda registrado con estado inicial y referencia al archivo original

## Hito 3 - Cola de procesamiento y jobs

Objetivo:
desacoplar por completo la subida del procesamiento documental.

Entregables:

- tabla o entidad `ProcessingJob`
- creador de jobs al subir documentos
- cola de procesamiento
- worker independiente del flujo HTTP
- estados tecnicos del job
- reintentos basicos y captura de errores

Definicion de terminado:

- el usuario puede subir documentos sin esperar al OCR
- los trabajos se procesan por detras
- el sistema puede mostrar estado de cola, procesando, procesado o error

## Hito 4 - Extraccion documental reutilizando el motor actual

Objetivo:
conectar el worker con una primera version util del pipeline de extraccion.

Entregables:

- adaptador entre job de procesamiento y `ai-service`
- soporte para PDF e imagen
- extraccion de campos minimos:
  - proveedor
  - fecha
  - numero de factura
  - base imponible
  - impuesto
  - total
  - moneda
  - tipo de documento
- guardado de resultado, warnings y confianza

Regla importante:

- se reutiliza primero lo que ya funciona del proyecto actual
- la optimizacion profunda del OCR o del modelo se hace despues de tener el flujo completo estable

Definicion de terminado:

- al completar un job, el documento pasa a `pendiente_revision`
- existe un resultado estructurado consultable por la web

## Hito 5 - Bandeja de revision

Objetivo:
dar a la asesoria una pantalla operativa de trabajo diario.

Entregables:

- listado de documentos pendientes
- filtros basicos por empresa, estado, fecha y canal
- detalle del documento
- visor del PDF o imagen original
- vista de datos extraidos
- indicadores de warnings y confianza

Definicion de terminado:

- una persona de la asesoria puede entrar en una cola de trabajo real y revisar documentos sin salir de la app

## Hito 6 - Edicion, aceptar, rechazar y reprocesar

Objetivo:
cerrar el ciclo humano del MVP documental.

Entregables:

- edicion manual de campos extraidos
- accion de aceptar
- accion de rechazar con motivo
- accion de reprocesar
- registro de auditoria de cada decision

Definicion de terminado:

- cada documento puede terminar en un estado final claro
- el sistema conserva quien reviso, que cambio y cuando

## Hito 7 - Calidad operativa del MVP

Objetivo:
hacer que la primera version sea usable de verdad y no solo funcional.

Entregables:

- deteccion basica de posibles duplicados
- mejores mensajes de error
- feedback claro de estados en subida y revision
- metricas minimas de tiempo de procesamiento y tasa de error
- pruebas de lote con volumen controlado

Definicion de terminado:

- el sistema soporta un flujo realista de trabajo sin confusion en pantalla
- se puede medir si el OCR y la estructuracion estan rindiendo bien

---

## 6. Backlog priorizado

Orden recomendado de implementacion:

1. cerrar estados y modelo minimo del MVP
2. implementar autenticacion y contexto de asesoria
3. rehacer la subida multiple con la nueva semantica de documento y lote
4. introducir `ProcessingJob` y cola
5. conectar worker con el motor actual de extraccion
6. construir bandeja de revision
7. habilitar aceptar, rechazar y reprocesar
8. anadir duplicados, auditoria y mejoras de experiencia

---

## 7. Historias tecnicas iniciales

Estas son las primeras historias que conviene abrir:

### Historia 1

Como usuario de asesoria, quiero iniciar sesion y trabajar dentro de mi contexto para no mezclar empresas de otras asesorias.

### Historia 2

Como usuario de asesoria, quiero seleccionar una empresa cliente antes de subir documentos para que cada factura quede correctamente asociada.

### Historia 3

Como usuario de asesoria, quiero subir varios PDFs e imagenes en un mismo lote para ahorrar tiempo de operativa.

### Historia 4

Como sistema, quiero registrar un job por documento para poder procesar en segundo plano y mostrar estados fiables.

### Historia 5

Como revisor, quiero ver el original y los datos extraidos en una sola pantalla para decidir rapido si el resultado es valido.

### Historia 6

Como revisor, quiero corregir un campo, aceptar o rechazar para cerrar cada documento con trazabilidad.

---

## 8. Aterrizaje sobre el repo actual

Para no perder tiempo, el arranque puede apoyarse en la estructura ya existente:

- `frontend/`
  - reutilizar base de React y las pantallas que sirvan como punto de partida
- `backend/`
  - convertirlo en API de negocio del MVP documental
- `ai-service/`
  - reutilizar extraccion actual como primer motor de procesamiento
- `database/`
  - redefinir migraciones para el nuevo modelo minimo
- `storage/`
  - usarlo solo como soporte local de desarrollo

Esto implica una regla practica:

- primero reorganizar lo justo para arrancar
- despues refactorizar en profundidad cuando el flujo documental ya exista de extremo a extremo

---

## 9. Lo que queda explicitamente fuera

En esta fase no se construye todavia:

- propuesta de asiento contable final
- validacion contable avanzada
- plan contable completo
- contrapartidas
- sincronizacion con ERP
- portal de empresa cliente
- workflow dual cliente -> asesoria
- almacenamiento BLOB como decision cerrada

---

## 10. Riesgos a vigilar desde el principio

- que la subida siga acoplada al procesamiento y bloquee la UX
- que se mezclen estados de negocio y estados tecnicos
- que la extraccion actual se trate como definitiva en lugar de provisional
- que la revision humana quede pobre y obligue a salir de la app
- que el modelo de datos documental se contamine demasiado pronto con conceptos contables

---

## 11. Criterio para pasar a fase 2

Solo se deberia abrir la fase contable cuando el MVP documental cumpla esto:

- la subida multiple funciona de forma estable
- el procesamiento asincrono esta resuelto
- la asesoria puede revisar de manera comoda
- aceptar, rechazar y reprocesar funcionan con trazabilidad
- existe una calidad de extraccion suficientemente util para trabajo real

Cuando eso ocurra, la siguiente fase sera:

- propuesta contable
- asiento borrador
- persistencia final de contabilizacion
- integraciones externas
