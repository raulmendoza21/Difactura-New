const auditRepo = require('../repositories/auditRepository');

async function log({ usuario_id, factura_id, accion, detalle, ip }) {
  return auditRepo.create({
    usuario_id,
    factura_id,
    accion,
    detalle_json: detalle || null,
    ip_address: ip || null,
  });
}

async function getByFactura(facturaId) {
  return auditRepo.findByFactura(facturaId);
}

async function getLatestByFacturaAndAction(facturaId, action) {
  return auditRepo.findLatestByFacturaAndAction(facturaId, action);
}

async function getRecent(limit) {
  return auditRepo.findRecent(limit);
}

module.exports = { log, getByFactura, getLatestByFacturaAndAction, getRecent };
