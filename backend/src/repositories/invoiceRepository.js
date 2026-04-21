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

// Extrae campos del JSON para búsqueda/ordenación sin perder el blob completo
function jsonField(key) {
  return `f.documento_json->>'${key}'`;
}

async function findAll({
  asesoriaId,
  estado,
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
    fecha_factura: `(f.documento_json->>'fecha')`,
    total: `(f.documento_json->>'total')::numeric`,
    proveedor: `(f.documento_json->>'proveedor')`,
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
    // Permitir buscar por nuestro identificador propio (DOC-000123) o numero suelto.
    // Si el termino (sin prefijo) es un entero, lo intentamos casar contra:
    //   * f.numero_correlativo cuando la consulta esta acotada a una empresa.
    //   * f.id como fallback global (vista de asesoria).
    const idMatch = String(search).trim().toUpperCase().replace(/^DOC-?/, '').replace(/^0+/, '');
    const numericId = /^\d+$/.test(idMatch) ? parseInt(idMatch, 10) : null;

    if (numericId !== null) {
      conditions.push(`(
        f.numero_correlativo = $${paramIndex + 1}
        OR f.id = $${paramIndex + 1}
        OR COALESCE(f.documento_json->>'numero_factura', '') ILIKE $${paramIndex}
        OR COALESCE(f.documento_json->>'proveedor', '') ILIKE $${paramIndex}
        OR COALESCE(c.nombre, '') ILIKE $${paramIndex}
        OR COALESCE(latest_document.nombre_archivo, '') ILIKE $${paramIndex}
      )`);
      params.push(`%${search}%`, numericId);
      paramIndex += 2;
    } else {
      conditions.push(`(
        COALESCE(f.documento_json->>'numero_factura', '') ILIKE $${paramIndex}
        OR COALESCE(f.documento_json->>'proveedor', '') ILIKE $${paramIndex}
        OR COALESCE(c.nombre, '') ILIKE $${paramIndex}
        OR COALESCE(latest_document.nombre_archivo, '') ILIKE $${paramIndex}
      )`);
      params.push(`%${search}%`);
      paramIndex += 1;
    }
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  const offset = (page - 1) * limit;
  const orderBy = sortByMap[sortBy] || sortByMap.created_at;
  const direction = String(sortDir).toUpperCase() === 'ASC' ? 'ASC' : 'DESC';

  const countResult = await db.query(`SELECT COUNT(*) ${baseFrom} ${where}`, params);
  const total = parseInt(countResult.rows[0].count, 10);

  const result = await db.query(
    `SELECT f.*,
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
            c.nombre AS cliente_nombre, c.cif AS cliente_cif, c.asesoria_id AS asesoria_id,
            u.nombre AS validado_por_nombre
     FROM facturas f
     LEFT JOIN clientes c ON f.cliente_id = c.id
     LEFT JOIN usuarios u ON f.validado_por = u.id
     WHERE f.id = $1`,
    [id]
  );
  return result.rows[0] || null;
}

async function create(data) {
  // El correlativo se asigna por empresa cliente: cada empresa ve sus facturas
  // numeradas desde 1 sin huecos. Lo hacemos en transaccion para evitar
  // condiciones de carrera entre uploads concurrentes del mismo cliente.
  if (!data.cliente_id) {
    // Sin cliente no hay correlativo: insercion simple (caso edge legacy).
    const result = await db.query(
      `INSERT INTO facturas (estado, cliente_id, confianza_ia)
       VALUES ($1, $2, $3)
       RETURNING *`,
      [data.estado || 'SUBIDA', null, data.confianza_ia || null]
    );
    return result.rows[0];
  }

  const client = await db.getClient();
  try {
    await client.query('BEGIN');

    // UPSERT atomico: incrementa el contador del cliente y nos devuelve el
    // nuevo valor. Sin race conditions porque la fila queda bloqueada por la
    // propia tx hasta el COMMIT.
    const seqResult = await client.query(
      `INSERT INTO cliente_secuencias (cliente_id, ultimo_correlativo, updated_at)
       VALUES ($1, 1, CURRENT_TIMESTAMP)
       ON CONFLICT (cliente_id) DO UPDATE
         SET ultimo_correlativo = cliente_secuencias.ultimo_correlativo + 1,
             updated_at = CURRENT_TIMESTAMP
       RETURNING ultimo_correlativo`,
      [data.cliente_id]
    );
    const numeroCorrelativo = seqResult.rows[0].ultimo_correlativo;

    const result = await client.query(
      `INSERT INTO facturas (estado, cliente_id, confianza_ia, numero_correlativo)
       VALUES ($1, $2, $3, $4)
       RETURNING *`,
      [
        data.estado || 'SUBIDA',
        data.cliente_id,
        data.confianza_ia || null,
        numeroCorrelativo,
      ]
    );

    await client.query('COMMIT');
    return result.rows[0];
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

async function update(id, data) {
  const fields = [];
  const params = [];
  let paramIndex = 1;

  const allowedFields = [
    'estado', 'confianza_ia', 'validado_por', 'fecha_procesado', 'documento_json', 'notas',
  ];

  for (const field of allowedFields) {
    if (data[field] !== undefined) {
      if (field === 'documento_json') {
        fields.push(`${field} = $${paramIndex++}`);
        params.push(typeof data[field] === 'string' ? data[field] : JSON.stringify(data[field]));
      } else {
        fields.push(`${field} = $${paramIndex++}`);
        params.push(data[field]);
      }
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

async function requeueStaleJobs(cutoffDate, { facturaId = null, maxRecoveries = 2 } = {}) {
  const client = await db.getClient();

  try {
    await client.query('BEGIN');

    const staleJobsResult = await client.query(
      `UPDATE processing_jobs
       SET estado = CASE
             WHEN retry_count + 1 >= $3 THEN 'ERROR'
             ELSE 'PENDIENTE'
           END,
           started_at = CASE
             WHEN retry_count + 1 >= $3 THEN started_at
             ELSE NULL
           END,
           finished_at = CASE
             WHEN retry_count + 1 >= $3 THEN NOW()
             ELSE NULL
           END,
           worker_id = CASE
             WHEN retry_count + 1 >= $3 THEN worker_id
             ELSE NULL
           END,
           retry_count = retry_count + 1,
           error_message = CASE
             WHEN retry_count + 1 >= $3 THEN
               CONCAT_WS(' | ', NULLIF(error_message, ''), 'Job marcado como error tras multiples recuperaciones automaticas')
             ELSE
               CONCAT_WS(' | ', NULLIF(error_message, ''), 'Job reencolado automaticamente tras quedar atascado')
           END
       WHERE estado = 'EN_PROCESO'
         AND started_at IS NOT NULL
         AND started_at < $1
         AND ($2::int IS NULL OR factura_id = $2)
       RETURNING *`,
      [cutoffDate, facturaId, maxRecoveries]
    );

    const pendingFacturaIds = staleJobsResult.rows
      .filter((job) => job.estado === 'PENDIENTE')
      .map((job) => job.factura_id);
    const errorFacturaIds = staleJobsResult.rows
      .filter((job) => job.estado === 'ERROR')
      .map((job) => job.factura_id);

    if (pendingFacturaIds.length > 0) {
      await client.query(
        `UPDATE facturas
         SET estado = 'SUBIDA',
             fecha_procesado = NULL
         WHERE id = ANY($1::int[])
           AND estado = 'EN_PROCESO'`,
        [pendingFacturaIds]
      );
    }

    if (errorFacturaIds.length > 0) {
      await client.query(
        `UPDATE facturas
         SET estado = 'ERROR_PROCESAMIENTO'
         WHERE id = ANY($1::int[])
           AND estado = 'EN_PROCESO'`,
        [errorFacturaIds]
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
