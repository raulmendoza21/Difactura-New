-- ============================================================
-- Difactura - Índices
-- Aceleran las consultas más frecuentes del sistema
-- ============================================================

-- ─── Facturas ───────────────────────────────────────────────────
CREATE INDEX idx_facturas_numero ON facturas (numero_factura);
CREATE INDEX idx_facturas_estado ON facturas (estado);
CREATE INDEX idx_facturas_fecha ON facturas (fecha);
CREATE INDEX idx_facturas_proveedor ON facturas (proveedor_id);
CREATE INDEX idx_facturas_cliente ON facturas (cliente_id);
CREATE INDEX idx_facturas_tipo ON facturas (tipo);
CREATE INDEX idx_facturas_created_at ON facturas (created_at);

-- ─── Proveedores ────────────────────────────────────────────────
CREATE UNIQUE INDEX idx_proveedores_cif ON proveedores (cif) WHERE cif IS NOT NULL;
CREATE INDEX idx_proveedores_nombre_norm ON proveedores (nombre_normalizado);

-- ─── Clientes ───────────────────────────────────────────────────
CREATE UNIQUE INDEX idx_clientes_cif ON clientes (cif) WHERE cif IS NOT NULL;
CREATE INDEX idx_clientes_nombre_norm ON clientes (nombre_normalizado);

-- ─── Productos y Servicios ──────────────────────────────────────
CREATE INDEX idx_productos_desc_norm ON productos_servicios (descripcion_normalizada);
CREATE INDEX idx_productos_categoria ON productos_servicios (categoria);

-- ─── Factura Líneas ─────────────────────────────────────────────
CREATE INDEX idx_factura_lineas_factura ON factura_lineas (factura_id);

-- ─── Documentos Subidos ─────────────────────────────────────────
CREATE INDEX idx_documentos_factura ON documentos_subidos (factura_id);
CREATE INDEX idx_documentos_hash ON documentos_subidos (hash_archivo);

-- ─── Processing Jobs ────────────────────────────────────────────
CREATE INDEX idx_jobs_factura ON processing_jobs (factura_id);
CREATE INDEX idx_jobs_estado ON processing_jobs (estado);

-- ─── Auditoría ──────────────────────────────────────────────────
CREATE INDEX idx_auditoria_factura ON auditoria_procesos (factura_id);
CREATE INDEX idx_auditoria_usuario ON auditoria_procesos (usuario_id);
CREATE INDEX idx_auditoria_created ON auditoria_procesos (created_at);
