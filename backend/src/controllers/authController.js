const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const db = require('../config/database');
const { jwtSecret, jwtExpiresIn, bcryptSaltRounds } = require('../config/auth');
const { UnauthorizedError, ConflictError } = require('../utils/errors');

async function login(req, res, next) {
  try {
    const { email, password } = req.body;

    const result = await db.query('SELECT * FROM usuarios WHERE email = $1 AND activo = TRUE', [email]);
    const user = result.rows[0];

    if (!user) {
      throw new UnauthorizedError('Credenciales inválidas');
    }

    const validPassword = await bcrypt.compare(password, user.password_hash);
    if (!validPassword) {
      throw new UnauthorizedError('Credenciales inválidas');
    }

    const token = jwt.sign(
      { id: user.id, email: user.email, nombre: user.nombre, rol: user.rol },
      jwtSecret,
      { expiresIn: jwtExpiresIn }
    );

    res.json({
      token,
      user: { id: user.id, email: user.email, nombre: user.nombre, rol: user.rol },
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

    const result = await db.query(
      `INSERT INTO usuarios (email, password_hash, nombre, rol)
       VALUES ($1, $2, $3, $4) RETURNING id, email, nombre, rol, activo, created_at`,
      [email, passwordHash, nombre, rol || 'LECTURA']
    );

    res.status(201).json({ user: result.rows[0] });
  } catch (err) {
    next(err);
  }
}

async function me(req, res) {
  const result = await db.query(
    'SELECT id, email, nombre, rol, activo, created_at FROM usuarios WHERE id = $1',
    [req.user.id]
  );
  res.json({ user: result.rows[0] });
}

module.exports = { login, register, me };
