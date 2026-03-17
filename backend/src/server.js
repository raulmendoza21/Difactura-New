const app = require('./app');
const fs = require('fs');
const storageConfig = require('./config/storage');

const PORT = process.env.PORT || 3000;

// Asegurar que existen los directorios de storage
for (const dir of [storageConfig.uploadsDir, storageConfig.processedDir]) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`Directorio creado: ${dir}`);
  }
}

app.listen(PORT, () => {
  console.log(`Difactura Backend corriendo en puerto ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/api/health`);
});
