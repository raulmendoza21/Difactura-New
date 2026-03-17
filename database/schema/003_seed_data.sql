-- ============================================================
-- Difactura - Datos Iniciales (Seed)
-- Usuario administrador y datos base para desarrollo
-- ============================================================

-- ─── Usuario administrador ──────────────────────────────────────
-- Email: admin@difactura.local
-- Password: Admin123!
-- Hash generado con bcrypt (12 salt rounds)
INSERT INTO usuarios (email, password_hash, nombre, rol, activo)
VALUES (
    'admin@difactura.local',
    '$2b$12$5aap1aYXHgkfxIh4KPCY2utktsLMW6oMcGIV9ojks8MJbsU3kiAH6',
    'Administrador',
    'ADMIN',
    TRUE
);

-- ─── Proveedores de ejemplo (desarrollo) ────────────────────────
INSERT INTO proveedores (nombre, nombre_normalizado, cif, direccion, email, telefono) VALUES
('Suministros García S.L.', 'SUMINISTROS GARCIA', 'B12345678', 'Calle Mayor 10, Madrid', 'info@suministrosgarcia.es', '912345678'),
('Tecnología Avanzada S.A.', 'TECNOLOGIA AVANZADA', 'A87654321', 'Av. de la Industria 5, Barcelona', 'contacto@tecavanzada.com', '934567890'),
('Servicios Profesionales López', 'SERVICIOS PROFESIONALES LOPEZ', 'B11223344', 'Plaza España 3, Valencia', 'admin@splopez.es', '963456789');

-- ─── Clientes de ejemplo (desarrollo) ──────────────────────────
INSERT INTO clientes (nombre, nombre_normalizado, cif, direccion, email, telefono) VALUES
('Distribuciones Martínez S.L.', 'DISTRIBUCIONES MARTINEZ', 'B99887766', 'Calle Comercio 15, Sevilla', 'pedidos@dmartinez.es', '954321098'),
('Hostelería del Sur S.A.', 'HOSTELERIA DEL SUR', 'A55443322', 'Av. Andalucía 22, Málaga', 'reservas@hostelsur.com', '952345678');
