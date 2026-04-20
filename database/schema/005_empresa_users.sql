-- ============================================================
-- Difactura - Usuarios de empresa (empleados de clientes)
-- Permite que empleados de empresas cliente suban documentos
-- que luego la asesoria revisa y valida.
-- ============================================================

-- 1. Nuevo tipo de usuario: ASESORIA (actual) o EMPRESA (nuevo)
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS tipo_usuario VARCHAR(20) NOT NULL DEFAULT 'ASESORIA'
        CHECK (tipo_usuario IN ('ASESORIA', 'EMPRESA'));

-- 2. Relacion opcional con la empresa cliente
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS cliente_id INTEGER REFERENCES clientes(id) ON DELETE RESTRICT;

-- 3. Ampliar roles permitidos para incluir EMPRESA_UPLOAD
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_rol_check;
ALTER TABLE usuarios
    ADD CONSTRAINT usuarios_rol_check
        CHECK (rol IN ('ADMIN', 'CONTABILIDAD', 'REVISOR', 'LECTURA', 'EMPRESA_UPLOAD'));

-- 4. Constraint: si tipo_usuario = EMPRESA, cliente_id es obligatorio
ALTER TABLE usuarios
    ADD CONSTRAINT chk_empresa_requires_cliente
        CHECK (tipo_usuario = 'ASESORIA' OR cliente_id IS NOT NULL);

-- 5. Indice para buscar usuarios por empresa
CREATE INDEX IF NOT EXISTS idx_usuarios_cliente ON usuarios (cliente_id)
    WHERE cliente_id IS NOT NULL;
