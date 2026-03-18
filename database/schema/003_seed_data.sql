-- ============================================================
-- Difactura - Seed inicial
-- ============================================================

-- Asesoria de ejemplo
INSERT INTO asesorias (nombre, estado)
VALUES ('Asesoria Central Demo', 'ACTIVA');

-- Usuario administrador
-- Email: admin@difactura.local
-- Password: Admin123!
INSERT INTO usuarios (asesoria_id, email, password_hash, nombre, rol, activo)
VALUES (
    1,
    'admin@difactura.local',
    '$2b$12$5aap1aYXHgkfxIh4KPCY2utktsLMW6oMcGIV9ojks8MJbsU3kiAH6',
    'Administrador',
    'ADMIN',
    TRUE
);

-- Usuario revisor
INSERT INTO usuarios (asesoria_id, email, password_hash, nombre, rol, activo)
VALUES (
    1,
    'revisor@difactura.local',
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

-- Empresas cliente de ejemplo
INSERT INTO clientes (asesoria_id, nombre, nombre_normalizado, cif, direccion, email, telefono, estado) VALUES
(1, 'Distribuciones Martinez S.L.', 'DISTRIBUCIONES MARTINEZ', 'B99887766', 'Calle Comercio 15, Sevilla', 'pedidos@dmartinez.es', '954321098', 'ACTIVA'),
(1, 'Hosteleria del Sur S.A.', 'HOSTELERIA DEL SUR', 'A55443322', 'Av. Andalucia 22, Malaga', 'reservas@hostelsur.com', '952345678', 'ACTIVA'),
(1, 'Construcciones Acosta S.L.', 'CONSTRUCCIONES ACOSTA', 'B33445566', 'Poligono La Vega 7, Las Palmas', 'facturas@acosta.es', '928123456', 'ACTIVA');
