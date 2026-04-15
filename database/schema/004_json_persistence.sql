-- ============================================================
-- Difactura - Migración a persistencia JSON
-- Toda la extracción se guarda en documento_json JSONB.
-- Se eliminan las tablas fragmentadas de líneas, proveedores
-- y productos que ya no son necesarias.
-- ============================================================

-- 1. Eliminar tablas que ya no son necesarias
DROP TABLE IF EXISTS factura_lineas CASCADE;
DROP TABLE IF EXISTS productos_servicios CASCADE;

-- Quitar FK de facturas → proveedores antes de borrar la tabla
ALTER TABLE facturas DROP COLUMN IF EXISTS proveedor_id;
DROP TABLE IF EXISTS proveedores CASCADE;

-- 2. Eliminar índices de columnas que se van a borrar
DROP INDEX IF EXISTS idx_facturas_numero;
DROP INDEX IF EXISTS idx_facturas_fecha;
DROP INDEX IF EXISTS idx_facturas_proveedor;
DROP INDEX IF EXISTS idx_facturas_tipo;
DROP INDEX IF EXISTS idx_factura_lineas_factura;
DROP INDEX IF EXISTS idx_proveedores_cif;
DROP INDEX IF EXISTS idx_proveedores_nombre_norm;
DROP INDEX IF EXISTS idx_productos_desc_norm;
DROP INDEX IF EXISTS idx_productos_categoria;

-- 3. Modificar tabla facturas:
--    - Añadir columna documento_json
--    - Eliminar columnas de datos fragmentados
ALTER TABLE facturas
    ADD COLUMN IF NOT EXISTS documento_json JSONB,
    DROP COLUMN IF EXISTS numero_factura,
    DROP COLUMN IF EXISTS tipo,
    DROP COLUMN IF EXISTS fecha,
    DROP COLUMN IF EXISTS base_imponible,
    DROP COLUMN IF EXISTS iva_porcentaje,
    DROP COLUMN IF EXISTS iva_importe,
    DROP COLUMN IF EXISTS total,
    DROP COLUMN IF EXISTS notas;

-- El CHECK constraint de estado sigue igual (SUBIDA, EN_PROCESO, etc.)
-- Se mantienen: id, cliente_id, estado, confianza_ia, validado_por,
--               fecha_procesado, created_at, updated_at, documento_json

-- 4. Nuevos índices para consultas sobre el JSON
CREATE INDEX IF NOT EXISTS idx_facturas_json
    ON facturas USING GIN (documento_json);

-- Índices sobre campos extraídos del JSON para ordenación/filtrado rápidos
CREATE INDEX IF NOT EXISTS idx_facturas_json_numero
    ON facturas ((documento_json->>'numero_factura'));

CREATE INDEX IF NOT EXISTS idx_facturas_json_fecha
    ON facturas ((documento_json->>'fecha'));

CREATE INDEX IF NOT EXISTS idx_facturas_json_total
    ON facturas (((documento_json->>'total')::numeric))
    WHERE documento_json->>'total' IS NOT NULL;
