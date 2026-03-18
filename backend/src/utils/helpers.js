const crypto = require('crypto');
const { v4: uuidv4 } = require('uuid');

function normalizeName(name) {
  if (!name) return null;

  return name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // quitar tildes
    .toUpperCase()
    .replace(/\b(S\.?L\.?U?\.?|S\.?A\.?U?\.?|S\.?C\.?|C\.?B\.?)\b/g, '') // sufijos societarios
    .replace(/[.,;:'"]/g, '') // puntuacion
    .replace(/\s+/g, ' ') // espacios multiples
    .trim();
}

function generateFileHash(buffer) {
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

function generateUniqueFilename(originalName) {
  const ext = originalName.split('.').pop();
  return `${uuidv4()}.${ext}`;
}

function generateUploadBatchId() {
  const timestamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14);
  return `upl_${timestamp}_${uuidv4().slice(0, 8)}`;
}

function formatDateForPg(date) {
  if (!date) return null;
  if (date instanceof Date) return date.toISOString();
  return date;
}

function isValidCif(cif) {
  if (!cif) return false;
  return /^[A-Z]\d{7}[A-Z0-9]$/i.test(cif.trim());
}

module.exports = {
  normalizeName,
  generateFileHash,
  generateUniqueFilename,
  generateUploadBatchId,
  formatDateForPg,
  isValidCif,
};
