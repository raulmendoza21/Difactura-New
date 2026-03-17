const db = require('../config/database');

async function findAll() {
  const result = await db.query('SELECT * FROM clientes ORDER BY nombre');
  return result.rows;
}

async function findById(id) {
  const result = await db.query('SELECT * FROM clientes WHERE id = $1', [id]);
  return result.rows[0] || null;
}

async function findByCif(cif) {
  const result = await db.query('SELECT * FROM clientes WHERE cif = $1', [cif]);
  return result.rows[0] || null;
}

async function findByNormalizedName(name) {
  const result = await db.query(
    'SELECT * FROM clientes WHERE nombre_normalizado = $1',
    [name]
  );
  return result.rows[0] || null;
}

async function create(data) {
  const result = await db.query(
    `INSERT INTO clientes (nombre, nombre_normalizado, cif, direccion, email, telefono)
     VALUES ($1, $2, $3, $4, $5, $6) RETURNING *`,
    [data.nombre, data.nombre_normalizado, data.cif, data.direccion, data.email, data.telefono]
  );
  return result.rows[0];
}

async function update(id, data) {
  const fields = [];
  const params = [];
  let paramIndex = 1;

  for (const field of ['nombre', 'nombre_normalizado', 'cif', 'direccion', 'email', 'telefono']) {
    if (data[field] !== undefined) {
      fields.push(`${field} = $${paramIndex++}`);
      params.push(data[field]);
    }
  }

  if (fields.length === 0) return findById(id);

  params.push(id);
  const result = await db.query(
    `UPDATE clientes SET ${fields.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
    params
  );
  return result.rows[0] || null;
}

module.exports = { findAll, findById, findByCif, findByNormalizedName, create, update };
