const db = require('../config/database');

async function create({ usuario_id, factura_id, accion, detalle_json, ip_address }) {
  const result = await db.query(
    `INSERT INTO auditoria_procesos (usuario_id, factura_id, accion, detalle_json, ip_address)
     VALUES ($1, $2, $3, $4, $5) RETURNING *`,
    [usuario_id, factura_id, accion, detalle_json ? JSON.stringify(detalle_json) : null, ip_address]
  );
  return result.rows[0];
}

async function findByFactura(facturaId) {
  const result = await db.query(
    `SELECT a.*, u.nombre AS usuario_nombre
     FROM auditoria_procesos a
     LEFT JOIN usuarios u ON a.usuario_id = u.id
     WHERE a.factura_id = $1
     ORDER BY a.created_at DESC`,
    [facturaId]
  );
  return result.rows;
}

async function findRecent(limit = 20) {
  const result = await db.query(
    `SELECT a.*, u.nombre AS usuario_nombre, f.numero_factura
     FROM auditoria_procesos a
     LEFT JOIN usuarios u ON a.usuario_id = u.id
     LEFT JOIN facturas f ON a.factura_id = f.id
     ORDER BY a.created_at DESC
     LIMIT $1`,
    [limit]
  );
  return result.rows;
}

module.exports = { create, findByFactura, findRecent };
