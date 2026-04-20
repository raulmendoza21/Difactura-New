const path = require('path');

const storagePath = process.env.STORAGE_PATH || './storage';

module.exports = {
  uploadsDir: path.resolve(storagePath, 'uploads'),
  processedDir: path.resolve(storagePath, 'processed'),
  maxFileSize: parseInt(process.env.MAX_FILE_SIZE || '10485760', 10),
  allowedMimeTypes: ['application/pdf', 'image/jpeg', 'image/png', 'image/tiff', 'image/webp'],
};
