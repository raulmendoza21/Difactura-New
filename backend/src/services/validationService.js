function validateAmounts(base, ivaPercent, ivaAmount, total) {
  const warnings = [];

  if (base != null && ivaPercent != null && ivaAmount != null) {
    const expectedIva = +(base * ivaPercent / 100).toFixed(2);
    if (Math.abs(expectedIva - ivaAmount) > 0.02) {
      warnings.push(`IVA calculado (${expectedIva}) no coincide con el detectado (${ivaAmount})`);
    }
  }

  if (base != null && ivaAmount != null && total != null) {
    const expectedTotal = +(base + ivaAmount).toFixed(2);
    if (Math.abs(expectedTotal - total) > 0.02) {
      warnings.push(`Total calculado (${expectedTotal}) no coincide con el detectado (${total})`);
    }
  }

  return warnings;
}

function validateCif(cif) {
  if (!cif) return false;
  const cleaned = cif.trim().toUpperCase();
  // CIF: letter + 7 digits + alphanumeric check
  if (/^[A-HJ-NP-SUVW]\d{7}[0-9A-J]$/.test(cleaned)) return true;
  // NIF: 8 digits + letter
  if (/^\d{8}[A-Z]$/.test(cleaned)) return true;
  // NIE: X/Y/Z + 7 digits + letter
  if (/^[XYZ]\d{7}[A-Z]$/.test(cleaned)) return true;
  return false;
}

module.exports = { validateAmounts, validateCif };
