const { ForbiddenError } = require('../utils/errors');

function roleMiddleware(...allowedRoles) {
  return (req, res, next) => {
    if (!req.user) {
      return next(new ForbiddenError('Usuario no autenticado'));
    }

    if (!allowedRoles.includes(req.user.rol)) {
      return next(new ForbiddenError('No tienes permisos para esta acción'));
    }

    next();
  };
}

module.exports = roleMiddleware;
