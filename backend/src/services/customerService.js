const customerRepo = require('../repositories/customerRepository');
const { normalizeName } = require('../utils/helpers');

async function findAll() {
  return customerRepo.findAll();
}

async function findById(id) {
  return customerRepo.findById(id);
}

async function findOrCreateByCif(nombre, cif) {
  if (cif) {
    const existing = await customerRepo.findByCif(cif);
    if (existing) return existing;
  }

  const nombreNorm = normalizeName(nombre);
  if (nombreNorm) {
    const existing = await customerRepo.findByNormalizedName(nombreNorm);
    if (existing) return existing;
  }

  return customerRepo.create({
    nombre,
    nombre_normalizado: nombreNorm,
    cif: cif || null,
  });
}

async function update(id, data) {
  if (data.nombre) {
    data.nombre_normalizado = normalizeName(data.nombre);
  }
  return customerRepo.update(id, data);
}

module.exports = { findAll, findById, findOrCreateByCif, update };
