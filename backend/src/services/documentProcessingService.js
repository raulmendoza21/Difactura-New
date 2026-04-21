const invoiceRepo = require('../repositories/invoiceRepository');
const aiClient = require('./aiClientService');
const auditService = require('./auditService');
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
      detalle: { job_id: job.id, worker_id: job.worker_id },
    });

    // Llamar al motor ai-service-vision
    const engineResult = await aiClient.processInvoice(document.ruta_storage, document.tipo_mime, {
      name: factura.cliente_nombre || '',
      taxId: factura.cliente_cif || '',
    });

    const confianza = Number(engineResult.confianza) || 0;
    // Unificado: toda factura procesada por la IA queda en PENDIENTE_REVISION
    // a la espera de validacion humana. La confianza queda guardada para que
    // la UI pueda destacar las que necesitan mas atencion.
    const nuevoEstado = INVOICE_STATES.PENDIENTE_REVISION;

    // Guardar el JSON completo extraído por el motor
    await invoiceRepo.update(factura.id, {
      estado: nuevoEstado,
      confianza_ia: confianza,
      fecha_procesado: new Date(),
      documento_json: engineResult,
    });

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
        confianza,
        operation_side: engineResult.operation_side || null,
        tipo_factura: engineResult.tipo_factura || engineResult.document_type || null,
        numero_factura: engineResult.numero_factura || null,
        provider: engineResult.provider || null,
        pages: engineResult.pages || null,
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
      detalle: { job_id: job.id, mensaje: error.message },
    });

    throw error;
  }
}

module.exports = { processJob };
