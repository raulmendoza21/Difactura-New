-- ============================================================
-- Difactura - Indices
-- ============================================================

-- Asesorias y usuarios
CREATE INDEX idx_usuarios_asesoria ON usuarios (asesoria_id);
CREATE INDEX idx_usuarios_asesoria_email ON usuarios (asesoria_id, email);

-- Facturas
CREATE INDEX idx_facturas_numero ON facturas (numero_factura);
CREATE INDEX idx_facturas_estado ON facturas (estado);
CREATE INDEX idx_facturas_fecha ON facturas (fecha);
CREATE INDEX idx_facturas_proveedor ON facturas (proveedor_id);
CREATE INDEX idx_facturas_cliente ON facturas (cliente_id);
CREATE INDEX idx_facturas_tipo ON facturas (tipo);
CREATE INDEX idx_facturas_created_at ON facturas (created_at);

-- Proveedores
CREATE UNIQUE INDEX idx_proveedores_cif ON proveedores (cif) WHERE cif IS NOT NULL;
CREATE INDEX idx_proveedores_nombre_norm ON proveedores (nombre_normalizado);

-- Empresas cliente
CREATE INDEX idx_clientes_asesoria ON clientes (asesoria_id);
CREATE INDEX idx_clientes_asesoria_nombre_norm ON clientes (asesoria_id, nombre_normalizado);
CREATE UNIQUE INDEX idx_clientes_asesoria_cif ON clientes (asesoria_id, cif) WHERE cif IS NOT NULL;

-- Productos y servicios
CREATE INDEX idx_productos_desc_norm ON productos_servicios (descripcion_normalizada);
CREATE INDEX idx_productos_categoria ON productos_servicios (categoria);

-- Factura lineas
CREATE INDEX idx_factura_lineas_factura ON factura_lineas (factura_id);

-- Documentos
CREATE INDEX idx_documentos_factura ON documentos_subidos (factura_id);
CREATE INDEX idx_documentos_hash ON documentos_subidos (hash_archivo);
CREATE INDEX idx_documentos_batch ON documentos_subidos (batch_id);

-- Jobs
CREATE INDEX idx_jobs_factura ON processing_jobs (factura_id);
CREATE INDEX idx_jobs_estado ON processing_jobs (estado);

-- Auditoria
CREATE INDEX idx_auditoria_factura ON auditoria_procesos (factura_id);
CREATE INDEX idx_auditoria_usuario ON auditoria_procesos (usuario_id);
CREATE INDEX idx_auditoria_created ON auditoria_procesos (created_at);
