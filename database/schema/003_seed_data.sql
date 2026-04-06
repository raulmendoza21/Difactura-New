-- ============================================================
-- Difactura - Seed inicial
-- ============================================================

-- Asesoria de ejemplo
INSERT INTO asesorias (nombre, estado)
VALUES ('Asesoria Central Demo', 'ACTIVA');

-- Usuario administrador demo
INSERT INTO usuarios (asesoria_id, email, password_hash, nombre, rol, activo)
VALUES (
    1,
    'admin@local.test',
    '$2b$12$5aap1aYXHgkfxIh4KPCY2utktsLMW6oMcGIV9ojks8MJbsU3kiAH6',
    'Administrador',
    'ADMIN',
    TRUE
);

-- Usuario revisor demo
INSERT INTO usuarios (asesoria_id, email, password_hash, nombre, rol, activo)
VALUES (
    1,
    'revisor@local.test',
    '$2b$12$5aap1aYXHgkfxIh4KPCY2utktsLMW6oMcGIV9ojks8MJbsU3kiAH6',
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
(1, 'Empresa Cliente Demo SL', 'EMPRESA CLIENTE DEMO', 'B44556622', 'Calle Ejemplo 15, Las Palmas de Gran Canaria', 'administracion@cliente-demo.test', '928000000', 'ACTIVA');
