const { AppError } = require('../utils/errors');

function errorHandler(err, req, res, next) {
  if (err instanceof AppError) {
    return res.status(err.statusCode).json({
      error: true,
      message: err.message,
    });
  }

  // Error de Multer (tamaño de archivo, tipo, etc.)
  if (err.code === 'LIMIT_FILE_SIZE') {
    return res.status(400).json({
      error: true,
      message: 'El archivo supera el tamaño máximo permitido (10MB)',
    });
  }

  console.error('Error no controlado:', err);

  res.status(500).json({
    error: true,
    message: 'Error interno del servidor',
  });
}

module.exports = errorHandler;
