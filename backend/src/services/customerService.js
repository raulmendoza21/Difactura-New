const customerRepo = require('../repositories/customerRepository');
const { normalizeName } = require('../utils/helpers');
const { ValidationError } = require('../utils/errors');

function ensureAdvisoryId(asesoriaId) {
  if (!asesoriaId) {
    throw new ValidationError('El contexto de asesoria es obligatorio');
  }
}

async function findAll(asesoriaId) {
  ensureAdvisoryId(asesoriaId);
  return customerRepo.findAll(asesoriaId);
}

async function findById(id, asesoriaId) {
  ensureAdvisoryId(asesoriaId);
  return customerRepo.findById(id, asesoriaId);
}

async function findOrCreateByCif(asesoriaId, nombre, cif) {
  ensureAdvisoryId(asesoriaId);

  if (cif) {
    const existingByCif = await customerRepo.findByCif(cif, asesoriaId);
    if (existingByCif) {
      return existingByCif;
    }
  }

  const nombreNormalizado = normalizeName(nombre);
  if (nombreNormalizado) {
    const existingByName = await customerRepo.findByNormalizedName(nombreNormalizado, asesoriaId);
    if (existingByName) {
      return existingByName;
    }
  }

  return customerRepo.create({
    asesoria_id: asesoriaId,
    nombre,
    nombre_normalizado: nombreNormalizado,
    cif: cif || null,
  });
}

async function update(id, asesoriaId, data) {
  ensureAdvisoryId(asesoriaId);

  if (data.nombre) {
    data.nombre_normalizado = normalizeName(data.nombre);
  }

  return customerRepo.update(id, asesoriaId, data);
}

module.exports = { findAll, findById, findOrCreateByCif, update };
