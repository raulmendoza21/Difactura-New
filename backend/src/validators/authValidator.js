const { ValidationError } = require('../utils/errors');

function validateLogin(req, res, next) {
  const { email, password } = req.body;

  if (!email || !password) {
    return next(new ValidationError('Email y contraseña son obligatorios'));
  }

  if (typeof email !== 'string' || !email.includes('@')) {
    return next(new ValidationError('Formato de email inválido'));
  }

  next();
}

function validateRegister(req, res, next) {
  const { email, password, nombre, rol } = req.body;

  if (!email || !password || !nombre) {
    return next(new ValidationError('Email, contraseña y nombre son obligatorios'));
  }

  if (typeof email !== 'string' || !email.includes('@')) {
    return next(new ValidationError('Formato de email inválido'));
  }

  if (password.length < 6) {
    return next(new ValidationError('La contraseña debe tener al menos 6 caracteres'));
  }

  const validRoles = ['ADMIN', 'CONTABILIDAD', 'REVISOR', 'LECTURA', 'EMPRESA_UPLOAD'];
  if (rol && !validRoles.includes(rol)) {
    return next(new ValidationError(`Rol inválido. Valores permitidos: ${validRoles.join(', ')}`));
  }

  next();
}

module.exports = { validateLogin, validateRegister };
