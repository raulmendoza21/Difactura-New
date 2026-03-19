const db = require('../config/database');

function mapInvoiceListRow(row) {
  const {
    job_id,
    job_estado,
    job_started_at,
    job_finished_at,
    job_error_message,
    job_retry_count,
    job_worker_id,
    job_created_at,
    documento_id,
    documento_batch_id,
    documento_canal_entrada,
    documento_fecha_subida,
    documento_nombre_archivo,
    ...invoice
  } = row;

  return {
    ...invoice,
    job: job_id
      ? {
          id: job_id,
          estado: job_estado,
          started_at: job_started_at,
          finished_at: job_finished_at,
          error_message: job_error_message,
          retry_count: job_retry_count,
          worker_id: job_worker_id,
          created_at: job_created_at,
        }
      : null,
    documento: documento_id
      ? {
          id: documento_id,
          batch_id: documento_batch_id,
          canal_entrada: documento_canal_entrada,
          fecha_subida: documento_fecha_subida,
          nombre_archivo: documento_nombre_archivo,
        }
      : null,
  };
}

async function findAll({
  asesoriaId,
  estado,
  tipo,
  companyId,
  channel,
  batchId,
  search,
  sortBy = 'created_at',
  sortDir = 'desc',
  page = 1,
  limit = 20,
} = {}) {
  const baseFrom = `
    FROM facturas f
    LEFT JOIN proveedores p ON f.proveedor_id = p.id
    LEFT JOIN clientes c ON f.cliente_id = c.id
    LEFT JOIN LATERAL (
      SELECT pj.*
      FROM processing_jobs pj
      WHERE pj.factura_id = f.id
      ORDER BY pj.created_at DESC
      LIMIT 1
    ) latest_job ON true
    LEFT JOIN LATERAL (
      SELECT ds.*
      FROM documentos_subidos ds
      WHERE ds.factura_id = f.id
      ORDER BY ds.fecha_subida DESC
      LIMIT 1
    ) latest_document ON true
  `;
  const conditions = [];
  const params = [];
  let paramIndex = 1;
  const sortByMap = {
    created_at: 'f.created_at',
    fecha_procesado: 'f.fecha_procesado',
    fecha_factura: 'f.fecha',
    total: 'f.total',
    proveedor: 'p.nombre',
    cliente: 'c.nombre',
    fecha_subida: 'latest_document.fecha_subida',
  };

  if (asesoriaId) {
    conditions.push(`c.asesoria_id = $${paramIndex++}`);
    params.push(asesoriaId);
  }

  if (estado) {
    conditions.push(`f.estado = $${paramIndex++}`);
    params.push(estado);
  }
  if (tipo) {
    conditions.push(`f.tipo = $${paramIndex++}`);
    params.push(tipo);
  }
  if (companyId) {
    conditions.push(`f.cliente_id = $${paramIndex++}`);
    params.push(companyId);
  }
  if (channel) {
    conditions.push(`latest_document.canal_entrada = $${paramIndex++}`);
    params.push(channel);
  }
  if (batchId) {
    conditions.push(`latest_document.batch_id = $${paramIndex++}`);
    params.push(batchId);
  }
  if (search) {
    conditions.push(`(
      COALESCE(f.numero_factura, '') ILIKE $${paramIndex}
      OR COALESCE(p.nombre, '') ILIKE $${paramIndex}
      OR COALESCE(c.nombre, '') ILIKE $${paramIndex}
      OR COALESCE(latest_document.nombre_archivo, '') ILIKE $${paramIndex}
      OR COALESCE(latest_document.batch_id, '') ILIKE $${paramIndex}
    )`);
    params.push(`%${search}%`);
    paramIndex += 1;
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  const offset = (page - 1) * limit;
  const orderBy = sortByMap[sortBy] || sortByMap.created_at;
  const direction = String(sortDir).toUpperCase() === 'ASC' ? 'ASC' : 'DESC';

  const countResult = await db.query(`SELECT COUNT(*) ${baseFrom} ${where}`, params);
  const total = parseInt(countResult.rows[0].count, 10);

  const result = await db.query(
    `SELECT f.*,
            p.nombre AS proveedor_nombre, p.cif AS proveedor_cif,
            c.nombre AS cliente_nombre, c.cif AS cliente_cif,
            latest_job.id AS job_id,
            latest_job.estado AS job_estado,
            latest_job.started_at AS job_started_at,
            latest_job.finished_at AS job_finished_at,
            latest_job.error_message AS job_error_message,
            latest_job.retry_count AS job_retry_count,
            latest_job.worker_id AS job_worker_id,
            latest_job.created_at AS job_created_at,
            latest_document.id AS documento_id,
            latest_document.batch_id AS documento_batch_id,
            latest_document.canal_entrada AS documento_canal_entrada,
            latest_document.fecha_subida AS documento_fecha_subida,
            latest_document.nombre_archivo AS documento_nombre_archivo
     ${baseFrom}
     ${where}
     ORDER BY ${orderBy} ${direction}, f.created_at DESC
     LIMIT $${paramIndex++} OFFSET $${paramIndex++}`,
    [...params, limit, offset]
  );

  return { data: result.rows.map(mapInvoiceListRow), total, page, limit };
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
    `INSERT INTO documentos_subidos (
        factura_id,
        usuario_subida_id,
        batch_id,
        canal_entrada,
        nombre_archivo,
        storage_key,
        ruta_storage,
        tipo_mime,
        tamano_bytes,
        hash_archivo
      )
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
     RETURNING *`,
    [
      data.factura_id,
      data.usuario_subida_id,
      data.batch_id,
      data.canal_entrada || 'web',
      data.nombre_archivo,
      data.storage_key,
      data.ruta_storage,
      data.tipo_mime,
      data.tamano_bytes,
      data.hash_archivo,
    ]
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

async function claimNextPendingJob(workerId) {
  const client = await db.getClient();

  try {
    await client.query('BEGIN');

    const result = await client.query(
      `WITH next_job AS (
         SELECT id
         FROM processing_jobs
         WHERE estado = 'PENDIENTE'
         ORDER BY created_at ASC
         FOR UPDATE SKIP LOCKED
         LIMIT 1
       )
       UPDATE processing_jobs pj
       SET estado = 'EN_PROCESO',
           started_at = NOW(),
           finished_at = NULL,
           error_message = NULL,
           worker_id = $1
       FROM next_job
       WHERE pj.id = next_job.id
       RETURNING pj.*`,
      [workerId]
    );

    await client.query('COMMIT');
    return result.rows[0] || null;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

async function requeueStaleJobs(cutoffDate) {
  const client = await db.getClient();

  try {
    await client.query('BEGIN');

    const staleJobsResult = await client.query(
      `UPDATE processing_jobs
       SET estado = 'PENDIENTE',
           started_at = NULL,
           finished_at = NULL,
           worker_id = NULL,
           retry_count = retry_count + 1,
           error_message = COALESCE(error_message, 'Job recuperado tras reinicio del worker')
       WHERE estado = 'EN_PROCESO'
         AND started_at IS NOT NULL
         AND started_at < $1
       RETURNING *`,
      [cutoffDate]
    );

    const facturaIds = staleJobsResult.rows.map((job) => job.factura_id);

    if (facturaIds.length > 0) {
      await client.query(
        `UPDATE facturas
         SET estado = 'SUBIDA'
         WHERE id = ANY($1::int[])`,
        [facturaIds]
      );
    }

    await client.query('COMMIT');
    return staleJobsResult.rows;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
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

async function countByEstado(asesoriaId, companyId) {
  const params = [asesoriaId];
  let whereClause = 'WHERE c.asesoria_id = $1';

  if (companyId) {
    params.push(companyId);
    whereClause += ' AND f.cliente_id = $2';
  }

  const result = await db.query(
    `SELECT f.estado, COUNT(*)::int AS count
     FROM facturas f
     INNER JOIN clientes c ON f.cliente_id = c.id
     ${whereClause}
     GROUP BY f.estado`,
    params
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
  claimNextPendingJob,
  requeueStaleJobs,
  updateJob,
  findJobByFactura,
  countByEstado,
};
