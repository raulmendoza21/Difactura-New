-- ============================================================
-- Difactura - Seed inicial
-- ============================================================

-- Asesoria de ejemplo
INSERT INTO asesorias (nombre, estado)
VALUES ('Asesoria Central Demo', 'ACTIVA');

-- Usuario administrador demo (password: admin123)
INSERT INTO usuarios (asesoria_id, email, password_hash, nombre, rol, activo)
VALUES (
    1,
    'admin@local.test',
    '$2b$12$N2iD5GeUvevibyMieL2jYelSA2tQwwVXx4YkV9xE19UrgNqzP86Bm',
    'Administrador',
    'ADMIN',
    TRUE
);

-- Usuario revisor demo (password: admin123)
INSERT INTO usuarios (asesoria_id, email, password_hash, nombre, rol, activo)
VALUES (
    1,
    'revisor@local.test',
    '$2b$12$N2iD5GeUvevibyMieL2jYelSA2tQwwVXx4YkV9xE19UrgNqzP86Bm',
    'Revisor Demo',
    'REVISOR',
    TRUE
);

-- Proveedores de ejemplo
INSERT INTO proveedores (nombre, nombre_normalizado, cif, direccion, email, telefono) VALUES
('Suministros Garcia S.L.', 'SUMINISTROS GARCIA', 'B12345678', 'Calle Mayor 10, Madrid', 'info@suministrosgarcia.es', '912345678'),
('Tecnologia Avanzada S.A.', 'TECNOLOGIA AVANZADA', 'A87654321', 'Av. de la Industria 5, Barcelona', 'contacto@tecavanzada.com', '934567890'),
('Servicios Profesionales Lopez', 'SERVICIOS PROFESIONALES LOPEZ', 'B11223344', 'Plaza Espana 3, Valencia', 'admin@splopez.es', '963456789');

-- Empresa cliente base
INSERT INTO clientes (asesoria_id, nombre, nombre_normalizado, cif, direccion, email, telefono, estado) VALUES
(1, 'Disoft Servicios SL', 'DISOFT', 'B35222249', 'Calle Ejemplo 15, Las Palmas de Gran Canaria', 'administracion@cliente-demo.test', '928000000', 'ACTIVA');

-- Usuario empresa demo (empleado de Disoft que puede subir documentos)
-- NOTA: este INSERT usa columnas que se crean en 005_empresa_users.sql,
--       por lo que se ejecuta desde un fichero seed posterior.

