const supplierService = require('../services/supplierService');

async function getAll(req, res, next) {
  try {
    const suppliers = await supplierService.findAll();
    res.json(suppliers);
  } catch (err) { next(err); }
}

async function getById(req, res, next) {
  try {
    const supplier = await supplierService.findById(parseInt(req.params.id, 10));
    if (!supplier) return res.status(404).json({ error: true, message: 'Proveedor no encontrado' });
    res.json(supplier);
  } catch (err) { next(err); }
}

async function update(req, res, next) {
  try {
    const supplier = await supplierService.update(parseInt(req.params.id, 10), req.body);
    if (!supplier) return res.status(404).json({ error: true, message: 'Proveedor no encontrado' });
    res.json(supplier);
  } catch (err) { next(err); }
}

module.exports = { getAll, getById, update };
