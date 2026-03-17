const db = require('../config/database');

async function findAll({ estado, tipo, page = 1, limit = 20 } = {}) {
  const conditions = [];
  const params = [];
  let paramIndex = 1;

  if (estado) {
    conditions.push(`f.estado = $${paramIndex++}`);
    params.push(estado);
  }
  if (tipo) {
    conditions.push(`f.tipo = $${paramIndex++}`);
    params.push(tipo);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  const offset = (page - 1) * limit;

  const countResult = await db.query(`SELECT COUNT(*) FROM facturas f ${where}`, params);
  const total = parseInt(countResult.rows[0].count, 10);

  const result = await db.query(
    `SELECT f.*,
            p.nombre AS proveedor_nombre, p.cif AS proveedor_cif,
            c.nombre AS cliente_nombre, c.cif AS cliente_cif
     FROM facturas f
     LEFT JOIN proveedores p ON f.proveedor_id = p.id
     LEFT JOIN clientes c ON f.cliente_id = c.id
     ${where}
     ORDER BY f.created_at DESC
     LIMIT $${paramIndex++} OFFSET $${paramIndex++}`,
    [...params, limit, offset]
  );

  return { data: result.rows, total, page, limit };
}

async function findById(id) {
  const result = await db.query(
    `SELECT f.*,
            p.nombre AS proveedor_nombre, p.cif AS proveedor_cif,
            c.nombre AS cliente_nombre, c.cif AS cliente_cif,
            u.nombre AS validado_por_nombre
     FROM facturas f
     LEFT JOIN proveedores p ON f.proveedor_id = p.id
     LEFT JOIN clientes c ON f.cliente_id = c.id
     LEFT JOIN usuarios u ON f.validado_por = u.id
     WHERE f.id = $1`,
    [id]
  );
  return result.rows[0] || null;
}

async function create(data) {
  const result = await db.query(
    `INSERT INTO facturas (numero_factura, tipo, fecha, proveedor_id, cliente_id,
     base_imponible, iva_porcentaje, iva_importe, total, estado, confianza_ia, notas)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
     RETURNING *`,
    [data.numero_factura, data.tipo, data.fecha, data.proveedor_id, data.cliente_id,
     data.base_imponible, data.iva_porcentaje, data.iva_importe, data.total,
     data.estado || 'SUBIDA', data.confianza_ia, data.notas]
  );
  return result.rows[0];
}

async function update(id, data) {
  const fields = [];
  const params = [];
  let paramIndex = 1;

  const allowedFields = [
    'numero_factura', 'tipo', 'fecha', 'proveedor_id', 'cliente_id',
    'base_imponible', 'iva_porcentaje', 'iva_importe', 'total',
    'estado', 'confianza_ia', 'validado_por', 'fecha_procesado', 'notas'
  ];

  for (const field of allowedFields) {
    if (data[field] !== undefined) {
      fields.push(`${field} = $${paramIndex++}`);
      params.push(data[field]);
    }
  }

  if (fields.length === 0) return findById(id);

  params.push(id);
  const result = await db.query(
    `UPDATE facturas SET ${fields.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
    params
  );
  return result.rows[0] || null;
}

async function findLines(facturaId) {
  const result = await db.query(
    'SELECT * FROM factura_lineas WHERE factura_id = $1 ORDER BY orden',
    [facturaId]
  );
  return result.rows;
}

async function createLines(facturaId, lines) {
  if (!lines || lines.length === 0) return [];

  const values = [];
  const params = [];
  let paramIndex = 1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    values.push(`($${paramIndex++}, $${paramIndex++}, $${paramIndex++}, $${paramIndex++}, $${paramIndex++}, $${paramIndex++})`);
    params.push(facturaId, line.descripcion, line.cantidad || 1, line.precio_unitario || 0, line.importe || line.subtotal || 0, i + 1);
  }

  const result = await db.query(
    `INSERT INTO factura_lineas (factura_id, descripcion, cantidad, precio_unitario, subtotal, orden)
     VALUES ${values.join(', ')} RETURNING *`,
    params
  );
  return result.rows;
}

async function deleteLines(facturaId) {
  await db.query('DELETE FROM factura_lineas WHERE factura_id = $1', [facturaId]);
}

async function findDocument(facturaId) {
  const result = await db.query(
    'SELECT * FROM documentos_subidos WHERE factura_id = $1',
    [facturaId]
  );
  return result.rows[0] || null;
}

async function findDocumentById(documentId) {
  const result = await db.query(
    'SELECT * FROM documentos_subidos WHERE id = $1',
    [documentId]
  );
  return result.rows[0] || null;
}

async function createDocument(data) {
  const result = await db.query(
    `INSERT INTO documentos_subidos (factura_id, nombre_archivo, ruta_storage, tipo_mime, tamano_bytes, hash_archivo)
     VALUES ($1, $2, $3, $4, $5, $6) RETURNING *`,
    [data.factura_id, data.nombre_archivo, data.ruta_storage, data.tipo_mime, data.tamano_bytes, data.hash_archivo]
  );
  return result.rows[0];
}

async function findByHash(hash) {
  const result = await db.query(
    'SELECT * FROM documentos_subidos WHERE hash_archivo = $1',
    [hash]
  );
  return result.rows[0] || null;
}

async function createJob(facturaId) {
  const result = await db.query(
    `INSERT INTO processing_jobs (factura_id, estado) VALUES ($1, 'PENDIENTE') RETURNING *`,
    [facturaId]
  );
  return result.rows[0];
}

async function updateJob(jobId, data) {
  const fields = [];
  const params = [];
  let paramIndex = 1;

  for (const field of ['estado', 'started_at', 'finished_at', 'error_message', 'retry_count', 'worker_id']) {
    if (data[field] !== undefined) {
      fields.push(`${field} = $${paramIndex++}`);
      params.push(data[field]);
    }
  }

  params.push(jobId);
  const result = await db.query(
    `UPDATE processing_jobs SET ${fields.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
    params
  );
  return result.rows[0] || null;
}

async function findJobByFactura(facturaId) {
  const result = await db.query(
    'SELECT * FROM processing_jobs WHERE factura_id = $1 ORDER BY created_at DESC LIMIT 1',
    [facturaId]
  );
  return result.rows[0] || null;
}

async function countByEstado() {
  const result = await db.query(
    'SELECT estado, COUNT(*)::int AS count FROM facturas GROUP BY estado'
  );
  return result.rows;
}

module.exports = {
  findAll,
  findById,
  create,
  update,
  findLines,
  createLines,
  deleteLines,
  findDocument,
  findDocumentById,
  createDocument,
  findByHash,
  createJob,
  updateJob,
  findJobByFactura,
  countByEstado,
};
