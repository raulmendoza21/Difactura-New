const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const db = require('../config/database');
const { jwtSecret, jwtExpiresIn, bcryptSaltRounds } = require('../config/auth');
const { UnauthorizedError, ConflictError } = require('../utils/errors');
const userRepository = require('../repositories/userRepository');

async function login(req, res, next) {
  try {
    const { email, password } = req.body;
    const user = await userRepository.findActiveByEmailWithAdvisory(email);

    if (!user) {
      throw new UnauthorizedError('Credenciales invalidas');
    }

    const validPassword = await bcrypt.compare(password, user.password_hash);
    if (!validPassword) {
      throw new UnauthorizedError('Credenciales invalidas');
    }

    const token = jwt.sign(
      {
        id: user.id,
        asesoria_id: user.asesoria_id,
        email: user.email,
        nombre: user.nombre,
        rol: user.rol,
      },
      jwtSecret,
      { expiresIn: jwtExpiresIn }
    );

    res.json({
      token,
      user: {
        id: user.id,
        email: user.email,
        nombre: user.nombre,
        rol: user.rol,
      },
      advisory: {
        id: user.advisory_id,
        nombre: user.advisory_nombre,
        estado: user.advisory_estado,
      },
    });
  } catch (err) {
    next(err);
  }
}

async function register(req, res, next) {
  try {
    const { email, password, nombre, rol } = req.body;

    const existing = await db.query('SELECT id FROM usuarios WHERE email = $1', [email]);
    if (existing.rows.length > 0) {
      throw new ConflictError('Ya existe un usuario con ese email');
    }

    const passwordHash = await bcrypt.hash(password, bcryptSaltRounds);
    const user = await userRepository.createWithinAdvisory({
      asesoriaId: req.user.asesoria_id,
      email,
      passwordHash,
      nombre,
      rol: rol || 'LECTURA',
    });

    res.status(201).json({ user });
  } catch (err) {
    next(err);
  }
}

async function me(req, res, next) {
  try {
    const user = await userRepository.findByIdWithAdvisory(req.user.id);

    if (!user) {
      throw new UnauthorizedError('Sesion no valida');
    }

    res.json({
      user: {
        id: user.id,
        email: user.email,
        nombre: user.nombre,
        rol: user.rol,
        activo: user.activo,
        created_at: user.created_at,
      },
      advisory: {
        id: user.advisory_id,
        nombre: user.advisory_nombre,
        estado: user.advisory_estado,
      },
    });
  } catch (err) {
    next(err);
  }
}

module.exports = { login, register, me };
