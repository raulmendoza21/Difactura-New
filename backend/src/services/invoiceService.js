const fs = require('fs');
const path = require('path');
const processingConfig = require('../config/processing');
const invoiceRepo = require('../repositories/invoiceRepository');
const auditService = require('./auditService');
const supplierService = require('./supplierService');
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
    tipo: 'compra',
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

  const lineas = await invoiceRepo.findLines(id);
  const documento = await invoiceRepo.findDocument(id);
  const job = await invoiceRepo.findJobByFactura(id);
  const latestExtraction = await auditService.getLatestByFacturaAndAction(id, 'PROCESADA_IA');

  const extraction = shouldExposeLatestExtraction(job, latestExtraction)
    ? {
        provider: latestExtraction.detalle_json.provider || null,
        method: latestExtraction.detalle_json.method || null,
        tipo_factura: latestExtraction.detalle_json.tipo_factura || null,
        confianza: latestExtraction.detalle_json.confianza ?? null,
        warnings: latestExtraction.detalle_json.warnings || [],
        document_input: latestExtraction.detalle_json.document_input || null,
        coverage: latestExtraction.detalle_json.coverage || null,
        field_confidence: latestExtraction.detalle_json.field_confidence || {},
        normalized_document: latestExtraction.detalle_json.normalized_document || null,
        evidence: latestExtraction.detalle_json.evidence || {},
        decision_flags: latestExtraction.detalle_json.decision_flags || [],
        company_match: latestExtraction.detalle_json.company_match || null,
        processing_trace: latestExtraction.detalle_json.processing_trace || [],
        created_at: latestExtraction.created_at,
      }
    : null;

  return {
    ...factura,
    empresa_asociada: factura.cliente_id
      ? {
          id: factura.cliente_id,
          nombre: factura.cliente_nombre,
          cif: factura.cliente_cif,
        }
      : null,
    lineas,
    documento,
    job,
    extraction,
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

  const staleCutoffDate = new Date(Date.now() - processingConfig.jobStaleMs);
  await invoiceRepo.requeueStaleJobs(staleCutoffDate, {
    facturaId: id,
    maxRecoveries: processingConfig.maxRecoveries,
  });

  const latestJob = await invoiceRepo.findJobByFactura(id);
  if (latestJob && [JOB_STATES.PENDIENTE, JOB_STATES.EN_PROCESO].includes(latestJob.estado)) {
    throw new ValidationError('La factura ya tiene un procesamiento en curso');
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

async function updateData(id, data, userId, asesoriaId, ip) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) {
    throw new NotFoundError('Factura no encontrada');
  }

  const payload = { ...data };

  if (Object.prototype.hasOwnProperty.call(data, 'proveedor_nombre') || Object.prototype.hasOwnProperty.call(data, 'proveedor_cif')) {
    const proveedorNombre = data.proveedor_nombre?.trim?.() || '';
    const proveedorCif = data.proveedor_cif?.trim?.() || '';

    if (proveedorNombre || proveedorCif) {
      const proveedor = await supplierService.findOrCreateByCif(proveedorNombre, proveedorCif);
      payload.proveedor_id = proveedor.id;
    } else {
      payload.proveedor_id = null;
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'cliente_nombre') || Object.prototype.hasOwnProperty.call(data, 'cliente_cif')) {
    const clienteNombre = data.cliente_nombre?.trim?.() || '';
    const clienteCif = data.cliente_cif?.trim?.() || '';

    if (clienteNombre || clienteCif) {
      const cliente = await customerService.findOrCreateByCif(asesoriaId, clienteNombre, clienteCif);
      payload.cliente_id = cliente.id;
    } else {
      payload.cliente_id = null;
    }
  }

  delete payload.proveedor_nombre;
  delete payload.proveedor_cif;
  delete payload.cliente_nombre;
  delete payload.cliente_cif;
  delete payload.lineas;

  await invoiceRepo.update(id, payload);

  if (data.lineas) {
    await invoiceRepo.deleteLines(id);
    await invoiceRepo.createLines(id, data.lineas);
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

function shouldExposeLatestExtraction(job, latestExtraction) {
  if (!latestExtraction?.detalle_json) {
    return false;
  }

  if (!job) {
    return true;
  }

  const extractionJobId = Number(latestExtraction.detalle_json.job_id || 0);
  if (extractionJobId && extractionJobId === Number(job.id)) {
    return true;
  }

  const latestExtractionCreatedAt = latestExtraction.created_at ? new Date(latestExtraction.created_at) : null;
  const latestJobCreatedAt = job.created_at ? new Date(job.created_at) : null;

  if (!latestExtractionCreatedAt || !latestJobCreatedAt) {
    return false;
  }

  return latestExtractionCreatedAt >= latestJobCreatedAt;
}
