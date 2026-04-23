# Difactura — plan de produccion (resumen)

1. Hetzner con dos nodos: `app-01` (CX32) publico y `db-01` (CX22 + volume) privado.
2. `app-01` corre **sin Docker y sin nginx**: systemd + Caddy (TLS automatico) + Node + Python nativos.
3. `db-01` corre PostgreSQL 15 nativo, accesible solo desde la red privada.
4. Los **originales** (PDF/JPG/PNG) se guardan en **Hetzner Object Storage (S3) desde el dia 1**, no en disco local.
5. A la IA se le sigue pasando la **mejor calidad util** (PDF -> PNG 300 DPI en RAM, EXIF + enhancements en fotos): ya esta implementado, no se toca.
6. **No se guardan imagenes intermedias**: son efimeras y reconstruibles desde el original.
7. Backups: `pg_dump` cifrado nocturno a un bucket S3 aparte (object storage es durable por si mismo).
8. Refactor minimo en backend: adaptador `S3Storage`, upload por buffer, descarga por URL firmada, eliminar `storage/processed/` y `nginx/`.
9. Seguridad: CORS cerrado al dominio, rate limiting en login y upload, firewall Hetzner, secretos en `.env` con permisos 640.
10. Resultado: `app-01` queda **stateless** (escalable y reemplazable), 1 sola maquina critica (`db-01`) y cero bloqueantes pendientes.

---

## Costes mensuales estimados

Modelo IA en uso: **gpt-5-mini** (~0,25 USD / 1M tokens entrada, ~2,00 USD / 1M tokens salida).
Por factura procesada: ~4.000 tokens entrada (imagen 300 DPI + prompt) + ~1.500 tokens salida ≈ **0,004 USD/factura ≈ 0,0037 EUR/factura**.

**Infraestructura fija (Hetzner):**

| Recurso | €/mes |
|---|---|
| `app-01` CX32 (4 vCPU / 8 GB) | ~7,50 |
| `db-01` CX22 (2 vCPU / 4 GB) | ~3,90 |
| Volume 40 GB para Postgres | ~1,90 |
| Object Storage ~50 GB (originales + backups) | ~0,60 |
| Dominio (.com/.es prorrateado) | ~1,00 |
| **Subtotal infraestructura** | **~15 EUR/mes** |

**Total segun volumen de facturas/mes:**

| Volumen | OpenAI | Infraestructura | **Total** |
|---|---|---|---|
| 500 facturas | ~2 EUR | 15 EUR | **~17 EUR/mes** |
| 2.000 facturas | ~7 EUR | 15 EUR | **~22 EUR/mes** |
| 10.000 facturas | ~37 EUR | 15 EUR | **~52 EUR/mes** |
| 50.000 facturas | ~185 EUR | 15-25 EUR | **~200-210 EUR/mes** |

Ancho de banda Hetzner incluye 20 TB/mes por VPS (gratis a este volumen). El crecimiento del bucket de originales suma ~1-2 EUR/mes por cada 100 GB acumulados.
