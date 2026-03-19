const invoiceRepo = require('../repositories/invoiceRepository');
const aiClient = require('./aiClientService');
const auditService = require('./auditService');
const supplierService = require('./supplierService');
const { INVOICE_STATES, JOB_STATES } = require('../utils/constants');
const { NotFoundError } = require('../utils/errors');

async function processJob(job) {
  const factura = await invoiceRepo.findById(job.factura_id);
  if (!factura) {
    throw new NotFoundError(`Factura ${job.factura_id} no encontrada para el job ${job.id}`);
  }

  const document = await invoiceRepo.findDocument(job.factura_id);
  if (!document) {
    throw new NotFoundError(`Documento no encontrado para la factura ${job.factura_id}`);
  }

  try {
    await invoiceRepo.update(factura.id, { estado: INVOICE_STATES.EN_PROCESO });

    await auditService.log({
      usuario_id: null,
      factura_id: factura.id,
      accion: 'PROCESAMIENTO_INICIADO',
      detalle: {
        job_id: job.id,
        worker_id: job.worker_id,
      },
    });

    const result = await aiClient.processInvoice(document.ruta_storage, document.tipo_mime);

    let proveedorId = null;

    if (result.proveedor || result.cif_proveedor) {
      const proveedor = await supplierService.findOrCreateByCif(result.proveedor, result.cif_proveedor);
      proveedorId = proveedor.id;
    }

    await invoiceRepo.update(factura.id, {
      numero_factura: result.numero_factura || null,
      tipo: result.tipo_factura || factura.tipo || 'compra',
      fecha: result.fecha || null,
      proveedor_id: proveedorId,
      cliente_id: factura.cliente_id,
      base_imponible: result.base_imponible || null,
      iva_porcentaje: result.iva_porcentaje || null,
      iva_importe: result.iva || null,
      total: result.total || null,
      confianza_ia: result.confianza,
      estado: INVOICE_STATES.PENDIENTE_REVISION,
      fecha_procesado: new Date(),
    });

    if (result.lineas && result.lineas.length > 0) {
      await invoiceRepo.deleteLines(factura.id);
      await invoiceRepo.createLines(factura.id, result.lineas);
    }

    await invoiceRepo.updateJob(job.id, {
      estado: JOB_STATES.COMPLETADO,
      finished_at: new Date(),
    });

    await auditService.log({
      usuario_id: null,
      factura_id: factura.id,
      accion: 'PROCESADA_IA',
      detalle: {
        job_id: job.id,
        provider: result.provider || null,
        method: result.method || null,
        confianza: result.confianza ?? null,
      },
    });
  } catch (error) {
    await invoiceRepo.update(factura.id, { estado: INVOICE_STATES.ERROR_PROCESAMIENTO });
    await invoiceRepo.updateJob(job.id, {
      estado: JOB_STATES.ERROR,
      finished_at: new Date(),
      error_message: error.message,
    });

    await auditService.log({
      usuario_id: null,
      factura_id: factura.id,
      accion: 'ERROR_PROCESAMIENTO',
      detalle: {
        job_id: job.id,
        mensaje: error.message,
      },
    });

    throw error;
  }
}

module.exports = {
  processJob,
};
