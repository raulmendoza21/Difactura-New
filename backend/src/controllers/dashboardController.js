const invoiceService = require('../services/invoiceService');
const auditService = require('../services/auditService');

async function getStats(req, res, next) {
  try {
    const estados = await invoiceService.getStats();
    const recentActivity = await auditService.getRecent(10);

    const totalFacturas = estados.reduce((sum, e) => sum + e.count, 0);
    const pendientes = estados.find((e) => e.estado === 'PENDIENTE_REVISION');
    const validadas = estados.find((e) => e.estado === 'VALIDADA');
    const errores = estados.find((e) => e.estado === 'ERROR_PROCESAMIENTO');

    res.json({
      total: totalFacturas,
      pendientes_revision: pendientes ? pendientes.count : 0,
      validadas: validadas ? validadas.count : 0,
      errores: errores ? errores.count : 0,
      por_estado: estados,
      actividad_reciente: recentActivity,
    });
  } catch (err) { next(err); }
}

module.exports = { getStats };
