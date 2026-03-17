const db = require('../config/database');

async function findAll() {
  const result = await db.query('SELECT * FROM productos_servicios ORDER BY descripcion');
  return result.rows;
}

async function findById(id) {
  const result = await db.query('SELECT * FROM productos_servicios WHERE id = $1', [id]);
  return result.rows[0] || null;
}

async function findByNormalizedDesc(desc) {
  const result = await db.query(
    'SELECT * FROM productos_servicios WHERE descripcion_normalizada = $1',
    [desc]
  );
  return result.rows[0] || null;
}

async function create(data) {
  const result = await db.query(
    `INSERT INTO productos_servicios (descripcion, descripcion_normalizada, precio_referencia, categoria)
     VALUES ($1, $2, $3, $4) RETURNING *`,
    [data.descripcion, data.descripcion_normalizada, data.precio_referencia, data.categoria]
  );
  return result.rows[0];
}

module.exports = { findAll, findById, findByNormalizedDesc, create };
