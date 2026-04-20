const fs = require('fs');
const path = require('path');
const processingConfig = require('../config/processing');
const invoiceRepo = require('../repositories/invoiceRepository');
const auditService = require('./auditService');
const customerService = require('./customerService');
const { generateFileHash, generateUploadBatchId } = require('../utils/helpers');
const { INVOICE_STATES, JOB_STATES } = require('../utils/constants');
const { NotFoundError, ValidationError } = require('../utils/errors');

async function uploadSingle(file, {
  userId,
  companyId,
  batchId,
  channel,
  ip,
}) {
  const fileBuffer = fs.readFileSync(file.path);
  const hash = generateFileHash(fileBuffer);

  const factura = await invoiceRepo.create({
    estado: INVOICE_STATES.SUBIDA,
    cliente_id: companyId,
  });

  const storageKey = path.basename(file.path);
  await invoiceRepo.createDocument({
    factura_id: factura.id,
    usuario_subida_id: userId,
    batch_id: batchId,
    canal_entrada: channel,
    nombre_archivo: file.originalname,
    storage_key: storageKey,
    ruta_storage: file.path,
    tipo_mime: file.mimetype,
    tamano_bytes: file.size,
    hash_archivo: hash,
  });

  const job = await invoiceRepo.createJob(factura.id);

  await auditService.log({
    usuario_id: userId,
    factura_id: factura.id,
    accion: 'SUBIDA',
    detalle: { archivo: file.originalname, tamano: file.size },
    ip,
  });

  return {
    factura,
    job,
    original_name: file.originalname,
    stored_name: storageKey,
    size_bytes: file.size,
    mime_type: file.mimetype,
    status: 'queued',
  };
}

async function uploadBatch(files, { userId, asesoriaId, companyId, channel, ip }) {
  if (!Array.isArray(files) || files.length === 0) {
    throw new ValidationError('Debes subir al menos un documento');
  }

  if (!companyId || Number.isNaN(companyId)) {
    throw new ValidationError('Debes seleccionar una empresa cliente antes de subir documentos');
  }

  const company = await customerService.findById(companyId, asesoriaId);
  if (!company) {
    throw new NotFoundError('La empresa cliente seleccionada no existe para esta asesoria');
  }

  const batchId = generateUploadBatchId();
  const documents = [];

  for (const file of files) {
    try {
      const uploaded = await uploadSingle(file, {
        userId,
        companyId,
        batchId,
        channel,
        ip,
      });
      documents.push(uploaded);
    } catch (error) {
      documents.push({
        original_name: file.originalname,
        size_bytes: file.size,
        mime_type: file.mimetype,
        status: 'failed',
        error: error.message,
      });
    }
  }

  const accepted = documents.filter((document) => document.status === 'queued');
  const failed = documents.filter((document) => document.status === 'failed');

  if (accepted.length === 0 && failed.length > 0) {
    throw new ValidationError(failed[0].error || 'No se pudo subir ningun documento');
  }

  return {
    batch_id: batchId,
    company: {
      id: company.id,
      nombre: company.nombre,
      cif: company.cif,
    },
    summary: {
      total: documents.length,
      accepted: accepted.length,
      failed: failed.length,
    },
    documents,
  };
}

async function getAll(filters) {
  return invoiceRepo.findAll(filters);
}

async function getById(id) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) {
    throw new NotFoundError('Factura no encontrada');
  }

  const documento = await invoiceRepo.findDocument(id);
  const job = await invoiceRepo.findJobByFactura(id);

  return {
    id: factura.id,
    cliente_id: factura.cliente_id,
    asesoria_id: factura.asesoria_id || null,
    estado: factura.estado,
    confianza_ia: factura.confianza_ia,
    validado_por: factura.validado_por,
    validado_por_nombre: factura.validado_por_nombre,
    fecha_procesado: factura.fecha_procesado,
    created_at: factura.created_at,
    updated_at: factura.updated_at,
    empresa_asociada: factura.cliente_id
      ? { id: factura.cliente_id, nombre: factura.cliente_nombre, cif: factura.cliente_cif }
      : null,
    documento_json: factura.documento_json || null,
    documento,
    job,
  };
}

async function getDocumentFile(documentId) {
  const document = await invoiceRepo.findDocumentById(documentId);
  if (!document) {
    throw new NotFoundError('Documento no encontrado');
  }

  return document;
}

async function validate(id, userId, ip) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) {
    throw new NotFoundError('Factura no encontrada');
  }

  const updated = await invoiceRepo.update(id, {
    estado: INVOICE_STATES.VALIDADA,
    validado_por: userId,
  });

  await auditService.log({
    usuario_id: userId,
    factura_id: id,
    accion: 'VALIDADA',
    ip,
  });

  return updated;
}

async function reject(id, userId, ip, motivo) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) {
    throw new NotFoundError('Factura no encontrada');
  }

  const updated = await invoiceRepo.update(id, {
    estado: INVOICE_STATES.RECHAZADA,
    validado_por: userId,
    notas: motivo || null,
  });

  await auditService.log({
    usuario_id: userId,
    factura_id: id,
    accion: 'RECHAZADA',
    detalle: { motivo },
    ip,
  });

  return updated;
}

async function reprocess(id, userId, ip) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) {
    throw new NotFoundError('Factura no encontrada');
  }

  // Check for active jobs FIRST, before requeuing stale ones
  const latestJob = await invoiceRepo.findJobByFactura(id);
  if (latestJob && [JOB_STATES.PENDIENTE, JOB_STATES.EN_PROCESO].includes(latestJob.estado)) {
    // If job is in EN_PROCESO but stale, requeue it and proceed
    const staleCutoffDate = new Date(Date.now() - processingConfig.jobStaleMs);
    if (latestJob.estado === JOB_STATES.EN_PROCESO && new Date(latestJob.updated_at) < staleCutoffDate) {
      await invoiceRepo.requeueStaleJobs(staleCutoffDate, {
        facturaId: id,
        maxRecoveries: processingConfig.maxRecoveries,
      });
    } else {
      throw new ValidationError('La factura ya tiene un procesamiento en curso');
    }
  }

  await invoiceRepo.update(id, {
    estado: INVOICE_STATES.SUBIDA,
    fecha_procesado: null,
    confianza_ia: null,
  });

  const job = await invoiceRepo.createJob(id);

  await auditService.log({
    usuario_id: userId,
    factura_id: id,
    accion: 'REPROCESO_SOLICITADO',
    detalle: { job_id: job.id },
    ip,
  });

  return getById(id);
}

async function updateData(id, data, userId, ip) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) {
    throw new NotFoundError('Factura no encontrada');
  }

  // Recibe { documento_json: {...} } — reemplaza el blob completo
  if (data.documento_json) {
    await invoiceRepo.update(id, { documento_json: data.documento_json });
  }

  await auditService.log({
    usuario_id: userId,
    factura_id: id,
    accion: 'EDITADA',
    detalle: { campos: Object.keys(data) },
    ip,
  });

  return getById(id);
}

async function getStats(asesoriaId, companyId) {
  return invoiceRepo.countByEstado(asesoriaId, companyId);
}

module.exports = {
  uploadBatch,
  getAll,
  getById,
  getDocumentFile,
  validate,
  reject,
  reprocess,
  updateData,
  getStats,
};
