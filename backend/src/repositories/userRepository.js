const db = require('../config/database');

const USER_WITH_ADVISORY_SELECT = `
  SELECT
    u.id,
    u.asesoria_id,
    u.email,
    u.password_hash,
    u.nombre,
    u.rol,
    u.activo,
    u.created_at,
    a.id AS advisory_id,
    a.nombre AS advisory_nombre,
    a.estado AS advisory_estado
  FROM usuarios u
  INNER JOIN asesorias a ON a.id = u.asesoria_id
`;

async function findActiveByEmailWithAdvisory(email) {
  const result = await db.query(
    `${USER_WITH_ADVISORY_SELECT}
     WHERE u.email = $1
       AND u.activo = TRUE
       AND a.estado = 'ACTIVA'`,
    [email]
  );

  return result.rows[0] || null;
}

async function findByIdWithAdvisory(id) {
  const result = await db.query(
    `${USER_WITH_ADVISORY_SELECT}
     WHERE u.id = $1`,
    [id]
  );

  return result.rows[0] || null;
}

async function createWithinAdvisory({ asesoriaId, email, passwordHash, nombre, rol }) {
  const result = await db.query(
    `INSERT INTO usuarios (asesoria_id, email, password_hash, nombre, rol)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING id, asesoria_id, email, nombre, rol, activo, created_at`,
    [asesoriaId, email, passwordHash, nombre, rol]
  );

  return result.rows[0];
}

module.exports = {
  findActiveByEmailWithAdvisory,
  findByIdWithAdvisory,
  createWithinAdvisory,
};
