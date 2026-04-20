const app = require('./app');
const fs = require('fs');
const storageConfig = require('./config/storage');
const processingWorkerService = require('./services/processingWorkerService');

const PORT = process.env.PORT || 3000;

// Asegurar que existen los directorios de storage
for (const dir of [storageConfig.uploadsDir, storageConfig.processedDir]) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`Directorio creado: ${dir}`);
  }
}

const server = app.listen(PORT, async () => {
  console.log(`Difactura Backend corriendo en puerto ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/api/health`);

  try {
    await processingWorkerService.start();
  } catch (error) {
    console.error(`No se pudo iniciar el worker de procesamiento: ${error.message}`);
  }
});

async function shutdown(signal) {
  console.log(`${signal} recibido. Cerrando servicios...`);

  // Safety timeout to force exit if graceful shutdown hangs
  const forceTimeout = setTimeout(() => {
    console.error('Shutdown forzado por timeout');
    process.exit(1);
  }, 10000);
  forceTimeout.unref();

  try {
    await processingWorkerService.stop();
  } catch (error) {
    console.error(`Error deteniendo worker: ${error.message}`);
  }

  server.close(() => {
    process.exit(0);
  });
}

process.on('SIGINT', () => {
  shutdown('SIGINT');
});

process.on('SIGTERM', () => {
  shutdown('SIGTERM');
});
