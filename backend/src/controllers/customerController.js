const customerService = require('../services/customerService');

async function getAll(req, res, next) {
  try {
    const customers = await customerService.findAll(req.user.asesoria_id);
    res.json({ data: customers });
  } catch (err) {
    next(err);
  }
}

async function getById(req, res, next) {
  try {
    const customer = await customerService.findById(parseInt(req.params.id, 10), req.user.asesoria_id);
    if (!customer) {
      return res.status(404).json({ error: true, message: 'Empresa cliente no encontrada' });
    }

    res.json({ data: customer });
  } catch (err) {
    next(err);
  }
}

async function update(req, res, next) {
  try {
    const customer = await customerService.update(
      parseInt(req.params.id, 10),
      req.user.asesoria_id,
      req.body
    );

    if (!customer) {
      return res.status(404).json({ error: true, message: 'Empresa cliente no encontrada' });
    }

    res.json({ data: customer });
  } catch (err) {
    next(err);
  }
}

module.exports = { getAll, getById, update };
