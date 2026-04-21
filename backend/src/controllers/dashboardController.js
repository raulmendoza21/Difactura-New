const invoiceService = require('../services/invoiceService');
const auditService = require('../services/auditService');

async function getStats(req, res, next) {
  try {
    const companyId = parseInt(req.headers['x-company-id'], 10);
    const estados = await invoiceService.getStats(
      req.user.asesoria_id,
      Number.isNaN(companyId) ? undefined : companyId
    );
    const recentActivity = await auditService.getRecent(10, req.user.asesoria_id);

    const totalFacturas = estados.reduce((sum, e) => sum + e.count, 0);
    const procesadasIa = estados.find((e) => e.estado === 'PROCESADA_IA');
    const pendientes = estados.find((e) => e.estado === 'PENDIENTE_REVISION');
    const validadas = estados.find((e) => e.estado === 'VALIDADA');
    const errores = estados.find((e) => e.estado === 'ERROR_PROCESAMIENTO');

    // PROCESADA_IA es un estado legacy que ahora se cuenta dentro de PENDIENTE_REVISION
    // (toda factura procesada espera validacion humana). Se suman para la UI y
    // se mantiene el campo `procesadas_ia` por compatibilidad.
    const pendientesCount = (pendientes ? pendientes.count : 0) + (procesadasIa ? procesadasIa.count : 0);

    res.json({
      total: totalFacturas,
      procesadas_ia: procesadasIa ? procesadasIa.count : 0,
      pendientes_revision: pendientesCount,
      validadas: validadas ? validadas.count : 0,
      errores: errores ? errores.count : 0,
      por_estado: estados,
      actividad_reciente: recentActivity,
    });
  } catch (err) { next(err); }
}

module.exports = { getStats };
