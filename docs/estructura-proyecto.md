# Difactura - Vision del producto y roadmap

## 1. Vision general

Difactura se redefine como una plataforma para asesorias que reciben, procesan y revisan facturas de empresas cliente.

El producto no se plantea ya como un simple extractor de facturas, sino como un flujo operativo completo:

1. recepcion de documentos
2. almacenamiento seguro
3. procesamiento asincrono
4. extraccion estructurada
5. revision humana
6. validacion final
7. evolucion posterior hacia propuesta y registro contable

La idea central es clara:

- la maquina acelera
- la asesoria revisa
- la confirmacion final sigue siendo humana

---

## 2. Alcance real del proyecto por etapas

## Etapa 1: MVP documental para asesoria

La primera etapa no intenta resolver todavia todo el problema contable.

Se centra solo en:

- subir documentos en lote
- procesarlos bien
- extraer datos de forma util
- revisarlos de forma comoda
- aceptar o rechazar el documento procesado

En esta etapa la plataforma funciona como una herramienta interna de la asesoria.

## Etapa 2: capa contable

Solo cuando la fase documental este estable se trabajara en:

- propuesta de asiento
- contrapartidas
- persistencia contable final
- integraciones con software externo

## Etapa 3: portal de empresa cliente

Mas adelante se incorporara el segundo tipo de actor:

- el usuario de empresa

Ese usuario podra:

- subir facturas
- revisar si la captura inicial es razonable
- enviarlas a la bandeja de la asesoria

Pero esa experiencia no forma parte del MVP inicial.

---

## 3. Usuario objetivo del MVP

En el MVP solo existe operativa para usuarios internos de asesorias.

Eso significa:

- login de usuario de asesoria
- contexto de asesoria
- seleccion de empresa cliente dentro de la asesoria
- subida, revision y validacion por personal de asesoria

No se implementa todavia:

- portal cliente
- doble bandeja cliente/asesoria
- validacion distribuida entre empresa y asesoria

---

## 4. Problema que resuelve el MVP

El MVP busca resolver esta parte del problema:

- recibir muchas facturas
- no bloquear la interfaz mientras se procesan
- extraer los datos clave de forma consistente
- permitir a la asesoria revisarlas con rapidez

El valor que se quiere demostrar no es aun la contabilizacion completa, sino que la recepcion y captura documental pueden hacerse de forma robusta y escalable.

---

## 5. Flujo funcional del MVP

## 5.1 Recepcion

Un usuario de asesoria entra en la plataforma y selecciona la empresa cliente con la que esta trabajando.

Desde ahi puede:

- subir multiples PDFs
- subir multiples imagenes
- usar movil para sacar fotos y enviarlas

Cada archivo queda asociado a:

- asesoria
- empresa cliente
- usuario que lo subio
- canal de entrada
- fecha y hora

## 5.2 Cola de procesamiento

Cuando un documento entra:

- se guarda el archivo
- se crea un job
- el usuario recibe confirmacion rapida
- el sistema procesa despues

La subida y el OCR no deben vivir en la misma espera interactiva.

## 5.3 Extraccion y estructuracion

El sistema debe intentar extraer como minimo:

- proveedor
- fecha
- numero de factura
- base imponible
- impuesto
- total
- moneda si existe
- tipo de documento

Y debe devolver:

- confianza
- warnings
- posibles duplicados

## 5.4 Revision humana

Las facturas procesadas aparecen en una bandeja de trabajo para la asesoria.

El usuario puede:

- ver el original
- ver los datos extraidos
- corregir campos
- aceptar la captura
- rechazarla
- pedir reproceso si hace falta

## 5.5 Validacion documental

En esta fase, validar significa:

- confirmar que los datos extraidos son suficientemente correctos
- dejar la factura lista para la siguiente etapa del producto

No implica todavia:

- registrar asiento definitivo
- cerrar contabilizacion
- exportar a ERP

---

## 6. Objetivos del MVP

La primera version funcional debe demostrar:

- subida multiple sin friccion
- captura usable desde movil y escritorio
- procesamiento asincrono estable
- buena calidad de extraccion
- bandeja de revision operativa
- trazabilidad del documento y de sus estados

Si eso no funciona bien, no tiene sentido entrar aun en asientos ni integraciones contables.

---

## 7. Lo que SI entra en el MVP

- autenticacion de usuarios de asesoria
- gestion basica de empresas cliente
- subida multiple de documentos
- almacenamiento documental con referencia persistente
- jobs y cola de procesamiento
- OCR y estructuracion de campos clave
- bandeja de pendientes
- detalle de revision
- correccion manual de datos
- aceptacion, rechazo y reproceso
- deteccion basica de duplicados
- auditoria de acciones

---

## 8. Lo que NO entra en el MVP

- propuesta de asiento contable final
- contrapartidas avanzadas
- plan contable completo
- exportacion a software contable
- portal de usuario empresa
- aprobacion multinivel
- automatizacion contable completa
- almacenamiento BLOB como decision cerrada

---

## 9. Estrategia de almacenamiento en esta etapa

Para el MVP documental, la recomendacion es:

- guardar el archivo fuera de la BD principal
- guardar en PostgreSQL la metadata y la referencia

Esto permite:

- escalar mejor
- simplificar backups
- servir el documento a la revision sin inflar la base de datos

La discusion BLOB vs object storage se deja para una etapa posterior de madurez, una vez validada la operativa documental.

---

## 10. Roadmap por fases

## Fase 1 - MVP documental de asesoria

Objetivo:

conseguir que la recepcion, extraccion y revision funcionen realmente bien

Entregables:

- login de asesoria
- seleccion de empresa cliente
- subida multiple
- procesamiento asincrono
- OCR/extraccion
- bandeja de revision
- aceptacion, rechazo y reproceso
- duplicados basicos
- auditoria

## Fase 2 - Robustez documental

Objetivo:

mejorar precision, rendimiento y gestion operativa

Entregables:

- mejor OCR
- mejores heuristicas de duplicado
- mas estados y filtros operativos
- mejores colas y reintentos
- mejor experiencia movil

## Fase 3 - Capa contable

Objetivo:

incorporar la propuesta contable y la persistencia de la informacion validada

Entregables:

- configuracion contable
- cuentas y contrapartidas
- propuesta de asiento
- validacion contable final
- persistencia del asiento

## Fase 4 - Portal empresa cliente e integraciones

Objetivo:

abrir el flujo a clientes y a sistemas externos

Entregables:

- portal empresa
- flujo empresa -> asesoria
- integraciones contables
- exportacion y sincronizacion

---

## 11. Criterios de exito de la Fase 1

La Fase 1 se dara por buena si:

- la asesoria puede subir lotes reales
- la app no se bloquea al procesar
- el porcentaje de capturas utiles es suficientemente alto
- la revision humana resulta comoda y rapida
- los documentos quedan trazados y recuperables

---

## 12. Preguntas abiertas

Estas decisiones quedan abiertas para aterrizarlas despues:

- si el usuario de asesoria puede trabajar con varias empresas al mismo tiempo o con una sola seleccionada
- si la aceptacion documental tendra varios estados o uno solo
- si la validacion documental y la validacion contable seran la misma accion o dos pasos distintos
- si la captura movil sera solo responsive o una PWA
