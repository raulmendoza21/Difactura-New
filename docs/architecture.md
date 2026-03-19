# Difactura - Arquitectura propuesta

## 1. Principio rector

La nueva arquitectura debe optimizar la primera necesidad del producto:

- recibir documentos bien
- procesarlos de forma desacoplada
- revisarlos con comodidad

No se va a construir primero la parte contable completa. La primera arquitectura debe estar pensada para una fase documental robusta y despues crecer hacia la capa contable.

La condicion para entrar en la capa contable es tener un contrato de datos estable entre documento normalizado y propuesta de asiento:

- ver `docs/contrato-datos-documentales-y-contables.md`

---

## 2. Enfoque recomendado

La recomendacion es una arquitectura modular con separacion clara entre:

- capa web
- API de negocio
- cola de trabajos
- worker de extraccion
- almacenamiento documental

No hace falta arrancar con microservicios complejos, pero si conviene separar los procesos pesados del flujo web.

La forma practica recomendada es:

- un backend principal modular
- uno o varios workers separados
- una cola
- un almacenamiento documental externo a la base principal

---

## 3. Componentes del MVP

## 3.1 Web app

Responsabilidades:

- login
- seleccion de empresa cliente
- subida multiple
- captura desde movil
- bandeja de pendientes
- revision humana

## 3.2 API de negocio

Responsabilidades:

- autenticar y dar contexto
- registrar documentos
- crear jobs
- servir bandejas y detalle
- aceptar, rechazar y reprocesar
- persistir estados y auditoria

## 3.3 Cola de procesamiento

Responsabilidades:

- desacoplar la subida del procesamiento
- permitir lotes grandes
- gestionar reintentos y errores

## 3.4 Worker de extraccion

Responsabilidades:

- OCR o extraccion textual
- estructuracion de datos
- devolucion de warnings y confianza
- calculo de metadatos tecnicos

## 3.5 Almacenamiento documental

Responsabilidades:

- conservar el original
- exponerlo a la pantalla de revision
- mantener integridad con hash y metadata

---

## 4. Lo que se deja fuera del primer corte arquitectonico

Aunque la arquitectura ya debe dejar espacio para ello, el MVP no necesita implementar todavia:

- motor contable completo
- persistencia de asiento final
- integracion con ERP
- portal empresa cliente

Esas piezas deben poder anadirse despues sin romper el flujo documental ya construido.

---

## 5. Flujo tecnico del MVP

1. El usuario de asesoria inicia sesion.
2. Selecciona una empresa cliente.
3. Sube uno o varios documentos.
4. El API guarda metadata y archivo.
5. El API crea un `processing_job` por documento.
6. La cola entrega trabajos al worker.
7. El worker procesa OCR y estructuracion.
8. El resultado se guarda como extraccion del documento.
9. El documento pasa a bandeja de revision.
10. Un humano acepta, corrige, rechaza o reprocesa.

---

## 6. Sincronia y asincronia

## Sincrono

- login
- seleccion de contexto
- alta de documento
- respuesta de recepcion
- consulta de bandejas
- carga del detalle
- acciones de aceptacion/rechazo

## Asincrono

- OCR
- interpretacion documental
- reprocesado
- tareas intensivas o en lote

Razon:

el tiempo de subida no debe depender del tiempo de OCR o del modelo.

---

## 7. Limites modulares del MVP

Los modulos que si conviene construir ya son:

- identity
- advisory-context
- companies
- documents
- document-storage
- processing-jobs
- extraction
- review
- duplicate-detection
- audit

Los modulos que solo quedan esbozados para fases posteriores son:

- accounting-configuration
- accounting-proposal
- accounting-posting
- external-integrations

---

## 8. Reutilizacion del proyecto actual

El proyecto actual no se debe arrastrar tal cual, pero si hay piezas aprovechables:

## Reutilizable ahora

- parte del `ai-service` como base de OCR y estructuracion
- logica de normalizacion documental ya explorada
- componentes de revision editable del frontend como referencia
- experiencia ya obtenida con estados y polling

## No reutilizar tal cual

- el flujo centrado en una sola factura subida y revisada al momento
- el acoplamiento actual entre backend y procesamiento
- el modelo orientado ya a validacion contable sin cerrar antes la fase documental

---

## 9. Estructura de proyecto recomendada para arrancar

```text
apps/
  web/
  api/
  worker-extraction/

packages/
  shared/
  ui/

docs/

infra/
  docker/
  compose/

database/
  migrations/
  seeds/
```

Dentro de `apps/api`:

```text
src/
  modules/
    identity/
    advisory-context/
    companies/
    documents/
    processing-jobs/
    review/
    duplicates/
    audit/
  shared/
  infrastructure/
```

---

## 10. Decision tecnica clave

La primera arquitectura no debe optimizar todavia la parte contable.

Debe optimizar:

- subida masiva
- captura desde movil
- cola estable
- buena extraccion
- buena revision

Si esa base funciona, la capa contable podra entrar encima con mucho menos riesgo.
