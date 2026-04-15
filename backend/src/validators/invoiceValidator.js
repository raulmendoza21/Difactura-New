const { ValidationError } = require('../utils/errors');
const { INVOICE_STATES } = require('../utils/constants');

function validateInvoiceUpdate(req, res, next) {
  const { documento_json } = req.body;

  if (documento_json !== undefined && (typeof documento_json !== 'object' || documento_json === null || Array.isArray(documento_json))) {
    return next(new ValidationError('documento_json debe ser un objeto JSON válido'));
  }

  next();
}

function validateStateTransition(req, res, next) {
  const { estado } = req.body;

  if (!estado) {
    return next(new ValidationError('Estado es obligatorio'));
  }

  const validStates = Object.values(INVOICE_STATES);
  if (!validStates.includes(estado)) {
    return next(new ValidationError(`Estado invalido. Valores permitidos: ${validStates.join(', ')}`));
  }

  next();
}

module.exports = { validateInvoiceUpdate, validateStateTransition };

