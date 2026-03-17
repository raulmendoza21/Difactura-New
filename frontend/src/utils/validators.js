export function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isValidCif(cif) {
  if (!cif || cif.length < 8 || cif.length > 10) return false;
  return /^[A-Za-z0-9]+$/.test(cif);
}

export function isPositiveNumber(value) {
  const num = Number(value);
  return !isNaN(num) && num > 0;
}

export function isValidFileType(file) {
  const allowed = ['application/pdf', 'image/jpeg', 'image/png', 'image/tiff'];
  return allowed.includes(file.type);
}

export function isValidFileSize(file, maxBytes = 10 * 1024 * 1024) {
  return file.size <= maxBytes;
}
