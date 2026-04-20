-- ============================================================
-- Difactura - Seed usuario empresa demo
-- Se ejecuta despues de 005_empresa_users.sql
-- ============================================================

-- Usuario empleado de Disoft que puede subir documentos
-- password: admin123 (mismo hash que los otros usuarios demo)
INSERT INTO usuarios (asesoria_id, email, password_hash, nombre, rol, activo, tipo_usuario, cliente_id)
VALUES (
    1,
    'empresa@disoft.test',
    '$2b$12$N2iD5GeUvevibyMieL2jYelSA2tQwwVXx4YkV9xE19UrgNqzP86Bm',
    'Empleado Disoft',
    'EMPRESA_UPLOAD',
    TRUE,
    'EMPRESA',
    1
);
