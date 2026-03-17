const multer = require('multer');
const path = require('path');
const storageConfig = require('../config/storage');
const { generateUniqueFilename } = require('../utils/helpers');

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, storageConfig.uploadsDir);
  },
  filename: (req, file, cb) => {
    cb(null, generateUniqueFilename(file.originalname));
  },
});

function fileFilter(req, file, cb) {
  if (storageConfig.allowedMimeTypes.includes(file.mimetype)) {
    cb(null, true);
  } else {
    cb(new Error('Tipo de archivo no permitido. Solo PDF, JPG y PNG'), false);
  }
}

const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: storageConfig.maxFileSize },
});

module.exports = upload;
