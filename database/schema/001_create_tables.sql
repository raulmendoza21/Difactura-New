-- ============================================================
-- Difactura - Creacion de tablas
-- Esquema base para el MVP documental
-- ============================================================

-- 1. Asesorias
CREATE TABLE asesorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVA'
        CHECK (estado IN ('ACTIVA', 'INACTIVA')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Usuarios internos de asesoria
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    asesoria_id INTEGER NOT NULL REFERENCES asesorias(id) ON DELETE RESTRICT,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'LECTURA'
        CHECK (rol IN ('ADMIN', 'CONTABILIDAD', 'REVISOR', 'LECTURA')),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Proveedores
CREATE TABLE proveedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    nombre_normalizado VARCHAR(255),
    cif VARCHAR(20) UNIQUE,
    direccion TEXT,
    email VARCHAR(255),
    telefono VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Empresas cliente de una asesoria
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    asesoria_id INTEGER NOT NULL REFERENCES asesorias(id) ON DELETE CASCADE,
    nombre VARCHAR(255) NOT NULL,
    nombre_normalizado VARCHAR(255),
    cif VARCHAR(20),
    direccion TEXT,
    email VARCHAR(255),
    telefono VARCHAR(30),
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVA'
        CHECK (estado IN ('ACTIVA', 'INACTIVA')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Productos y servicios
CREATE TABLE productos_servicios (
    id SERIAL PRIMARY KEY,
    descripcion VARCHAR(500) NOT NULL,
    descripcion_normalizada VARCHAR(500),
    precio_referencia NUMERIC(12, 2),
    categoria VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Facturas
CREATE TABLE facturas (
    id SERIAL PRIMARY KEY,
    numero_factura VARCHAR(100),
    tipo VARCHAR(10) NOT NULL DEFAULT 'compra'
        CHECK (tipo IN ('compra', 'venta')),
    fecha DATE,
    proveedor_id INTEGER REFERENCES proveedores(id) ON DELETE SET NULL,
    cliente_id INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
    base_imponible NUMERIC(12, 2),
    iva_porcentaje NUMERIC(5, 2),
    iva_importe NUMERIC(12, 2),
    total NUMERIC(12, 2),
    estado VARCHAR(25) NOT NULL DEFAULT 'SUBIDA'
        CHECK (estado IN (
            'SUBIDA', 'EN_PROCESO', 'PROCESADA_IA',
            'PENDIENTE_REVISION', 'VALIDADA', 'RECHAZADA',
            'SINCRONIZADA', 'ERROR_PROCESAMIENTO'
        )),
    confianza_ia NUMERIC(5, 2),
    validado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    fecha_procesado TIMESTAMPTZ,
    notas TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Lineas de factura
CREATE TABLE factura_lineas (
    id SERIAL PRIMARY KEY,
    factura_id INTEGER NOT NULL REFERENCES facturas(id) ON DELETE CASCADE,
    descripcion TEXT,
    cantidad NUMERIC(10, 3) DEFAULT 1,
    precio_unitario NUMERIC(12, 2),
    subtotal NUMERIC(12, 2),
    orden INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Documentos subidos
CREATE TABLE documentos_subidos (
    id SERIAL PRIMARY KEY,
    factura_id INTEGER REFERENCES facturas(id) ON DELETE CASCADE,
    usuario_subida_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    batch_id VARCHAR(64),
    canal_entrada VARCHAR(30) NOT NULL DEFAULT 'web'
        CHECK (canal_entrada IN ('web', 'mobile_camera', 'mobile_gallery')),
    nombre_archivo VARCHAR(500) NOT NULL,
    storage_key VARCHAR(1000),
    ruta_storage VARCHAR(1000) NOT NULL,
    tipo_mime VARCHAR(100) NOT NULL,
    tamano_bytes BIGINT,
    hash_archivo VARCHAR(64),
    fecha_subida TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Jobs de procesamiento
CREATE TABLE processing_jobs (
    id SERIAL PRIMARY KEY,
    factura_id INTEGER NOT NULL REFERENCES facturas(id) ON DELETE CASCADE,
    estado VARCHAR(15) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE', 'EN_PROCESO', 'COMPLETADO', 'ERROR')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    worker_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Auditoria
CREATE TABLE auditoria_procesos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    factura_id INTEGER REFERENCES facturas(id) ON DELETE SET NULL,
    accion VARCHAR(100) NOT NULL,
    detalle_json JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Funcion para autoactualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_asesorias_updated_at
    BEFORE UPDATE ON asesorias
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_usuarios_updated_at
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_proveedores_updated_at
    BEFORE UPDATE ON proveedores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_clientes_updated_at
    BEFORE UPDATE ON clientes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_productos_servicios_updated_at
    BEFORE UPDATE ON productos_servicios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_facturas_updated_at
    BEFORE UPDATE ON facturas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
