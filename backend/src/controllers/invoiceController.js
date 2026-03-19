const invoiceService = require('../services/invoiceService');

async function upload(req, res, next) {
  try {
    const files = [
      ...(req.files?.files || []),
      ...(req.files?.camera_files || []),
      ...(req.files?.file || []),
    ];

    if (files.length === 0) {
      return res.status(400).json({ error: true, message: 'No se ha proporcionado ningun archivo' });
    }

    const companyId = parseInt(req.body.company_id || req.headers['x-company-id'], 10);
    const channel = req.body.channel || 'web';

    const result = await invoiceService.uploadBatch(files, {
      userId: req.user.id,
      asesoriaId: req.user.asesoria_id,
      companyId,
      channel,
      ip: req.ip,
    });

    res.status(result.summary.failed > 0 ? 207 : 201).json(result);
  } catch (err) {
    next(err);
  }
}

async function getAll(req, res, next) {
  try {
    const { estado, tipo, page, limit, company_id, channel, batch_id, search, sort_by, sort_dir } = req.query;
    const companyHeaderId = parseInt(req.headers['x-company-id'], 10);
    const parsedCompanyId = company_id
      ? parseInt(company_id, 10)
      : (Number.isNaN(companyHeaderId) ? undefined : companyHeaderId);
    const result = await invoiceService.getAll({
      asesoriaId: req.user.asesoria_id,
      estado,
      tipo,
      companyId: parsedCompanyId,
      channel,
      batchId: batch_id,
      search,
      sortBy: sort_by,
      sortDir: sort_dir,
      page: page ? parseInt(page, 10) : 1,
      limit: limit ? parseInt(limit, 10) : 20,
    });
    res.json(result);
  } catch (err) {
    next(err);
  }
}

async function getById(req, res, next) {
  try {
    const factura = await invoiceService.getById(parseInt(req.params.id, 10));
    res.json(factura);
  } catch (err) {
    next(err);
  }
}

async function getDocumentFile(req, res, next) {
  try {
    const document = await invoiceService.getDocumentFile(parseInt(req.params.documentId, 10));
    res.type(document.tipo_mime);
    res.sendFile(document.ruta_storage);
  } catch (err) {
    next(err);
  }
}

async function validate(req, res, next) {
  try {
    const factura = await invoiceService.validate(parseInt(req.params.id, 10), req.user.id, req.ip);
    res.json(factura);
  } catch (err) {
    next(err);
  }
}

async function reject(req, res, next) {
  try {
    const { motivo } = req.body;
    const factura = await invoiceService.reject(parseInt(req.params.id, 10), req.user.id, req.ip, motivo);
    res.json(factura);
  } catch (err) {
    next(err);
  }
}

async function update(req, res, next) {
  try {
    const factura = await invoiceService.updateData(
      parseInt(req.params.id, 10),
      req.body,
      req.user.id,
      req.user.asesoria_id,
      req.ip
    );
    res.json(factura);
  } catch (err) {
    next(err);
  }
}

async function reprocess(req, res, next) {
  try {
    const factura = await invoiceService.reprocess(parseInt(req.params.id, 10), req.user.id, req.ip);
    res.json(factura);
  } catch (err) {
    next(err);
  }
}

module.exports = { upload, getAll, getById, getDocumentFile, validate, reject, update, reprocess };
