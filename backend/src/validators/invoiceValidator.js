const { ValidationError } = require('../utils/errors');
const { INVOICE_STATES } = require('../utils/constants');

function validateInvoiceUpdate(req, res, next) {
  const { tipo, fecha, base_imponible, iva_porcentaje, iva_importe, total, lineas } = req.body;

  if (tipo && !['compra', 'venta'].includes(tipo)) {
    return next(new ValidationError('Tipo debe ser "compra" o "venta"'));
  }

  if (fecha && isNaN(Date.parse(fecha))) {
    return next(new ValidationError('Formato de fecha invalido'));
  }

  const numericFields = { base_imponible, iva_porcentaje, iva_importe, total };
  for (const [field, value] of Object.entries(numericFields)) {
    if (value !== undefined && value !== null && (isNaN(value) || value < 0)) {
      return next(new ValidationError(`${field} debe ser un numero positivo`));
    }
  }

  if (lineas !== undefined) {
    if (!Array.isArray(lineas)) {
      return next(new ValidationError('lineas debe ser un array'));
    }

    for (const [index, line] of lineas.entries()) {
      if (!line || typeof line !== 'object') {
        return next(new ValidationError(`linea ${index + 1} invalida`));
      }

      const numericLineFields = {
        cantidad: line.cantidad,
        precio_unitario: line.precio_unitario,
        importe: line.importe ?? line.subtotal,
      };

      for (const [field, value] of Object.entries(numericLineFields)) {
        if (value !== undefined && value !== null && (isNaN(value) || value < 0)) {
          return next(new ValidationError(`linea ${index + 1}: ${field} debe ser un numero positivo`));
        }
      }
    }
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
