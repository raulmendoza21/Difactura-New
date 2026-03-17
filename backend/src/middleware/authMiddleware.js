const jwt = require('jsonwebtoken');
const { jwtSecret } = require('../config/auth');
const { UnauthorizedError } = require('../utils/errors');

function authMiddleware(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return next(new UnauthorizedError('Token no proporcionado'));
  }

  const token = authHeader.split(' ')[1];

  try {
    const decoded = jwt.verify(token, jwtSecret);
    req.user = decoded;
    next();
  } catch (err) {
    return next(new UnauthorizedError('Token inválido o expirado'));
  }
}

module.exports = authMiddleware;
