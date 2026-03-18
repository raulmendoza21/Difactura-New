# Difactura - Despliegue del MVP documental

## 1. Objetivo del despliegue

En esta fase el sistema debe poder operar bien el flujo documental de una asesoria:

- recibir lotes
- encolarlos
- procesarlos
- revisarlos

No se despliega todavia una capa contable completa.

---

## 2. Servicios necesarios para el MVP

Servicios minimos:

- web app
- API de negocio
- PostgreSQL
- cola o broker
- worker de extraccion
- almacenamiento documental

Opcionalmente:

- servicio de OCR/IA separado si tecnicamente compensa

---

## 3. Topologia recomendada

## Desarrollo local

- web
- api
- postgres
- redis o cola equivalente
- worker-extraction
- almacenamiento local compatible

## Staging

- misma topologia que el MVP real
- datos de prueba
- logs visibles por job

## Produccion inicial

- web
- api
- postgres
- redis
- uno o mas workers
- object storage o almacenamiento documental
- reverse proxy

---

## 4. Principio operativo

La regla de despliegue para esta fase es:

- la web recibe
- la API registra
- la cola distribuye
- el worker procesa

Si el worker tarda, la experiencia de usuario no se bloquea.

---

## 5. Almacenamiento documental

La opcion recomendada para el MVP es:

- archivo en filesystem gestionado o object storage
- metadata en PostgreSQL

No se recomienda cerrar ya la decision hacia BLOB como estrategia principal.

---

## 6. Observabilidad minima

Desde la primera version conviene tener:

- health checks
- logs por job
- estado visible por documento
- errores persistidos
- auditoria basica

Sin eso es dificil operar lotes reales.

---

## 7. Escalado esperado

En esta fase el escalado importante no es el del frontend, sino el de los workers.

El sistema debe poder:

- aceptar mas documentos de los que procesa en ese instante
- repartir trabajos
- reintentar si falla un documento

La cola es la pieza que hace posible ese comportamiento.

---

## 8. Preparacion para la siguiente fase

Aunque en esta etapa no se despliegue la capa contable, el despliegue debe dejar espacio para:

- nuevos workers
- integraciones externas
- servicios adicionales de negocio

Pero sin obligarnos a montarlos ya.
