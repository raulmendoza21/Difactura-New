const invoiceRepo = require('../repositories/invoiceRepository');
const aiClient = require('./aiClientService');
const auditService = require('./auditService');
const supplierService = require('./supplierService');
const documentEngineAdapter = require('./documentEngineAdapterService');
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

    const engineResult = await aiClient.processInvoice(document.ruta_storage, document.tipo_mime, {
      name: factura.cliente_nombre || '',
      taxId: factura.cliente_cif || '',
    });

    const {
      result,
      tipoFactura,
      counterparty,
    } = documentEngineAdapter.adaptEngineResultToCurrentModel(engineResult, factura);

    let proveedorId = null;

    if (counterparty?.name || counterparty?.taxId) {
      let proveedor = await supplierService.findOrCreateByCif(counterparty.name, counterparty.taxId);
      if (documentEngineAdapter.shouldRefreshStoredCounterparty(proveedor, counterparty, factura)) {
        proveedor = await supplierService.update(proveedor.id, {
          nombre: counterparty.name,
          cif: counterparty.taxId || proveedor.cif,
        });
      }
      proveedorId = proveedor.id;
    }

    await invoiceRepo.update(
      factura.id,
      documentEngineAdapter.buildCurrentPersistencePayload(result, factura, proveedorId),
    );

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
      detalle: documentEngineAdapter.buildCurrentAuditDetail(result, job.id, tipoFactura),
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
