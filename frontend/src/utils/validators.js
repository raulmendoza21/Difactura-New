export function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isValidCif(value) {
  if (!value) return false;
  const v = value.toUpperCase().replace(/[\s-]/g, '');
  if (v.length < 8 || v.length > 10) return false;

  // NIF personal: 8 dígitos + letra
  const nifMatch = v.match(/^(\d{8})([A-Z])$/);
  if (nifMatch) {
    const letters = 'TRWAGMYFPDXBNJZSQVHLCKE';
    return nifMatch[2] === letters[parseInt(nifMatch[1], 10) % 23];
  }

  // NIE: X/Y/Z + 7 dígitos + letra
  const nieMatch = v.match(/^([XYZ])(\d{7})([A-Z])$/);
  if (nieMatch) {
    const prefix = { X: '0', Y: '1', Z: '2' }[nieMatch[1]];
    const letters = 'TRWAGMYFPDXBNJZSQVHLCKE';
    return nieMatch[3] === letters[parseInt(prefix + nieMatch[2], 10) % 23];
  }

  // CIF: letra + 7 dígitos + dígito/letra control
  const cifMatch = v.match(/^([ABCDEFGHJKLMNPQRSUVW])(\d{7})([A-Z0-9])$/);
  if (cifMatch) {
    const digits = cifMatch[2].split('').map(Number);
    let sumA = 0;
    let sumB = 0;
    for (let i = 0; i < 7; i++) {
      if (i % 2 === 0) {
        const doubled = digits[i] * 2;
        sumB += doubled >= 10 ? Math.floor(doubled / 10) + (doubled % 10) : doubled;
      } else {
        sumA += digits[i];
      }
    }
    const control = (10 - ((sumA + sumB) % 10)) % 10;
    const controlLetter = 'JABCDEFGHI'[control];
    return cifMatch[3] === String(control) || cifMatch[3] === controlLetter;
  }

  return false;
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
