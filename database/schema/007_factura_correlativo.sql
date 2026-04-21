-- =====================================================================
-- 007_factura_correlativo.sql
-- Numeracion correlativa de facturas POR EMPRESA CLIENTE.
--
-- Objetivo: cada empresa cliente ve sus facturas numeradas de forma
-- limpia (DOC-000001, DOC-000002, ...). La asesoria sigue viendo todas
-- las facturas de sus empresas, distinguiendolas por la columna
-- "Empresa asociada".
--
-- Diseno:
--   * Tabla `cliente_secuencias` con un contador por cliente_id.
--   * Columna `facturas.numero_correlativo` denormalizada.
--   * Asignacion atomica via UPSERT en la insercion (ver invoiceRepository.create).
--
-- Idempotente: se puede ejecutar varias veces sin efectos secundarios.
-- =====================================================================

BEGIN;

-- 1) Tabla de secuencias por empresa cliente
CREATE TABLE IF NOT EXISTS cliente_secuencias (
    cliente_id INTEGER PRIMARY KEY REFERENCES clientes(id) ON DELETE CASCADE,
    ultimo_correlativo INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2) Columna numero_correlativo en facturas
ALTER TABLE facturas
    ADD COLUMN IF NOT EXISTS numero_correlativo INTEGER;

-- 3) Backfill de correlativos para facturas existentes:
--    asignamos numero secuencial por cliente_id ordenado por created_at, id.
--    Solo afecta a filas que aun no tienen numero_correlativo.
WITH numbered AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY cliente_id
               ORDER BY created_at ASC, id ASC
           ) AS correlativo
    FROM facturas
    WHERE numero_correlativo IS NULL
      AND cliente_id IS NOT NULL
)
UPDATE facturas f
SET numero_correlativo = n.correlativo
FROM numbered n
WHERE f.id = n.id;

-- 4) Sembrar cliente_secuencias con el maximo correlativo por cliente.
--    ON CONFLICT garantiza que si la tabla ya tenia datos, nos quedamos
--    con el mayor entre el actual y el calculado.
INSERT INTO cliente_secuencias (cliente_id, ultimo_correlativo, updated_at)
SELECT cliente_id, MAX(numero_correlativo), CURRENT_TIMESTAMP
FROM facturas
WHERE cliente_id IS NOT NULL
  AND numero_correlativo IS NOT NULL
GROUP BY cliente_id
ON CONFLICT (cliente_id) DO UPDATE
   SET ultimo_correlativo = GREATEST(cliente_secuencias.ultimo_correlativo, EXCLUDED.ultimo_correlativo),
       updated_at = CURRENT_TIMESTAMP;

-- 5) Indice unico parcial (numero_correlativo unico dentro de cada empresa).
--    Parcial para tolerar facturas huerfanas (cliente_id IS NULL tras un
--    posible ON DELETE SET NULL en el futuro) y facturas sin correlativo
--    aun (insercion en curso, casos edge).
CREATE UNIQUE INDEX IF NOT EXISTS idx_facturas_cliente_correlativo
    ON facturas (cliente_id, numero_correlativo)
    WHERE cliente_id IS NOT NULL AND numero_correlativo IS NOT NULL;

-- 6) Indice auxiliar para ordenar/filtrar por correlativo dentro de una empresa
CREATE INDEX IF NOT EXISTS idx_facturas_correlativo
    ON facturas (numero_correlativo)
    WHERE numero_correlativo IS NOT NULL;

COMMIT;
