const supplierRepo = require('../repositories/supplierRepository');
const { normalizeName } = require('../utils/helpers');

async function findAll() {
  return supplierRepo.findAll();
}

async function findById(id) {
  return supplierRepo.findById(id);
}

async function findOrCreateByCif(nombre, cif) {
  const nombreNorm = normalizeName(nombre);

  if (cif) {
    const existing = await supplierRepo.findByCif(cif);
    if (existing) {
      if (nombreNorm && existing.nombre_normalizado !== nombreNorm) {
        return supplierRepo.update(existing.id, {
          nombre,
          nombre_normalizado: nombreNorm,
          cif,
        });
      }
      return existing;
    }
  }

  if (nombreNorm) {
    const existing = await supplierRepo.findByNormalizedName(nombreNorm);
    if (existing) {
      if (cif && !existing.cif) {
        return supplierRepo.update(existing.id, { cif });
      }
      return existing;
    }
  }

  return supplierRepo.create({
    nombre,
    nombre_normalizado: nombreNorm,
    cif: cif || null,
  });
}

async function update(id, data) {
  if (data.nombre) {
    data.nombre_normalizado = normalizeName(data.nombre);
  }
  return supplierRepo.update(id, data);
}

module.exports = { findAll, findById, findOrCreateByCif, update };
