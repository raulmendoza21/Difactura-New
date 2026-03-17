const fs = require('fs');
const path = require('path');
const invoiceRepo = require('../repositories/invoiceRepository');
const aiClient = require('./aiClientService');
const auditService = require('./auditService');
const supplierService = require('./supplierService');
const customerService = require('./customerService');
const { generateFileHash } = require('../utils/helpers');
const { INVOICE_STATES, JOB_STATES } = require('../utils/constants');
const { ConflictError, NotFoundError } = require('../utils/errors');

async function upload(file, userId, ip) {
  // Verificar duplicado por hash
  const fileBuffer = fs.readFileSync(file.path);
  const hash = generateFileHash(fileBuffer);

  const existingDoc = await invoiceRepo.findByHash(hash);
  if (existingDoc) {
    fs.unlinkSync(file.path);
    throw new ConflictError('Este documento ya ha sido subido anteriormente');
  }

  // Crear factura en estado SUBIDA
  const factura = await invoiceRepo.create({
    estado: INVOICE_STATES.SUBIDA,
    tipo: 'compra',
  });

  // Guardar documento
  await invoiceRepo.createDocument({
    factura_id: factura.id,
    nombre_archivo: file.originalname,
    ruta_storage: file.path,
    tipo_mime: file.mimetype,
    tamano_bytes: file.size,
    hash_archivo: hash,
  });

  // Crear job de procesamiento
  const job = await invoiceRepo.createJob(factura.id);

  // Audit
  await auditService.log({
    usuario_id: userId,
    factura_id: factura.id,
    accion: 'SUBIDA',
    detalle: { archivo: file.originalname, tamano: file.size },
    ip,
  });

  // Lanzar procesamiento async
  processWithAI(factura.id, file.path, file.mimetype, job.id).catch((err) => {
    console.error(`Error procesando factura ${factura.id}:`, err.message);
  });

  return { factura, job };
}

async function processWithAI(facturaId, filePath, mimeType, jobId) {
  try {
    // Actualizar estado
    await invoiceRepo.update(facturaId, { estado: INVOICE_STATES.EN_PROCESO });
    await invoiceRepo.updateJob(jobId, { estado: JOB_STATES.EN_PROCESO, started_at: new Date() });

    // Llamar al servicio IA
    const result = await aiClient.processInvoice(filePath, mimeType);

    // Buscar o crear proveedor/cliente
    let proveedorId = null;
    let clienteId = null;

    if (result.proveedor || result.cif_proveedor) {
      const proveedor = await supplierService.findOrCreateByCif(result.proveedor, result.cif_proveedor);
      proveedorId = proveedor.id;
    }

    if (result.cliente || result.cif_cliente) {
      const cliente = await customerService.findOrCreateByCif(result.cliente, result.cif_cliente);
      clienteId = cliente.id;
    }

    // Actualizar factura con datos extraídos
    await invoiceRepo.update(facturaId, {
      numero_factura: result.numero_factura || null,
      tipo: result.tipo_factura || 'compra',
      fecha: result.fecha || null,
      proveedor_id: proveedorId,
      cliente_id: clienteId,
      base_imponible: result.base_imponible || null,
      iva_porcentaje: result.iva_porcentaje || null,
      iva_importe: result.iva || null,
      total: result.total || null,
      confianza_ia: result.confianza,
      estado: INVOICE_STATES.PENDIENTE_REVISION,
      fecha_procesado: new Date(),
    });

    // Crear líneas de factura
    if (result.lineas && result.lineas.length > 0) {
      await invoiceRepo.deleteLines(facturaId);
      await invoiceRepo.createLines(facturaId, result.lineas);
    }

    // Completar job
    await invoiceRepo.updateJob(jobId, { estado: JOB_STATES.COMPLETADO, finished_at: new Date() });
  } catch (err) {
    await invoiceRepo.update(facturaId, { estado: INVOICE_STATES.ERROR_PROCESAMIENTO });
    await invoiceRepo.updateJob(jobId, {
      estado: JOB_STATES.ERROR,
      finished_at: new Date(),
      error_message: err.message,
    });
    throw err;
  }
}

async function getAll(filters) {
  return invoiceRepo.findAll(filters);
}

async function getById(id) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) throw new NotFoundError('Factura no encontrada');

  const lineas = await invoiceRepo.findLines(id);
  const documento = await invoiceRepo.findDocument(id);
  const job = await invoiceRepo.findJobByFactura(id);

  return { ...factura, lineas, documento, job };
}

async function getDocumentFile(documentId) {
  const document = await invoiceRepo.findDocumentById(documentId);
  if (!document) throw new NotFoundError('Documento no encontrado');
  return document;
}

async function validate(id, userId, ip) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) throw new NotFoundError('Factura no encontrada');

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
  if (!factura) throw new NotFoundError('Factura no encontrada');

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

async function updateData(id, data, userId, ip) {
  const factura = await invoiceRepo.findById(id);
  if (!factura) throw new NotFoundError('Factura no encontrada');

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
      const cliente = await customerService.findOrCreateByCif(clienteNombre, clienteCif);
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

async function getStats() {
  return invoiceRepo.countByEstado();
}

module.exports = { upload, getAll, getById, getDocumentFile, validate, reject, updateData, getStats };
