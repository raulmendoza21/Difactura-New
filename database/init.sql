-- ============================================================
-- Difactura - Inicialización de Base de Datos
-- Este script se ejecuta automáticamente la primera vez
-- que el contenedor PostgreSQL arranca.
-- ============================================================

-- Crear extensiones útiles
CREATE EXTENSION IF NOT EXISTS "unaccent";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Otorgar permisos sobre el schema public al usuario
GRANT ALL ON SCHEMA public TO difactura_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO difactura_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO difactura_user;
