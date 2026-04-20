const { ForbiddenError } = require('../utils/errors');

/**
 * Middleware that restricts access to asesoria-only users.
 * Empresa users are blocked from accessing routes protected by this middleware.
 */
function asesoriaOnly(req, res, next) {
  if (!req.user) {
    return next(new ForbiddenError('Usuario no autenticado'));
  }

  if (req.user.tipo_usuario === 'EMPRESA') {
    return next(new ForbiddenError('Acceso restringido a usuarios de asesoria'));
  }

  next();
}

module.exports = { asesoriaOnly };
