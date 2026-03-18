const db = require('../config/database');

async function findAll(asesoriaId) {
  const result = await db.query(
    `SELECT *
     FROM clientes
     WHERE asesoria_id = $1
     ORDER BY nombre`,
    [asesoriaId]
  );

  return result.rows;
}

async function findById(id, asesoriaId) {
  const result = await db.query(
    `SELECT *
     FROM clientes
     WHERE id = $1
       AND asesoria_id = $2`,
    [id, asesoriaId]
  );

  return result.rows[0] || null;
}

async function findByCif(cif, asesoriaId) {
  const result = await db.query(
    `SELECT *
     FROM clientes
     WHERE cif = $1
       AND asesoria_id = $2`,
    [cif, asesoriaId]
  );

  return result.rows[0] || null;
}

async function findByNormalizedName(name, asesoriaId) {
  const result = await db.query(
    `SELECT *
     FROM clientes
     WHERE nombre_normalizado = $1
       AND asesoria_id = $2`,
    [name, asesoriaId]
  );

  return result.rows[0] || null;
}

async function create(data) {
  const result = await db.query(
    `INSERT INTO clientes (asesoria_id, nombre, nombre_normalizado, cif, direccion, email, telefono, estado)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
     RETURNING *`,
    [
      data.asesoria_id,
      data.nombre,
      data.nombre_normalizado,
      data.cif,
      data.direccion,
      data.email,
      data.telefono,
      data.estado || 'ACTIVA',
    ]
  );

  return result.rows[0];
}

async function update(id, asesoriaId, data) {
  const fields = [];
  const params = [];
  let paramIndex = 1;

  for (const field of ['nombre', 'nombre_normalizado', 'cif', 'direccion', 'email', 'telefono', 'estado']) {
    if (data[field] !== undefined) {
      fields.push(`${field} = $${paramIndex++}`);
      params.push(data[field]);
    }
  }

  if (fields.length === 0) {
    return findById(id, asesoriaId);
  }

  params.push(id, asesoriaId);
  const result = await db.query(
    `UPDATE clientes
     SET ${fields.join(', ')}
     WHERE id = $${paramIndex}
       AND asesoria_id = $${paramIndex + 1}
     RETURNING *`,
    params
  );

  return result.rows[0] || null;
}

module.exports = { findAll, findById, findByCif, findByNormalizedName, create, update };
