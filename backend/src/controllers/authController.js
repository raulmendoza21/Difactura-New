const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const db = require('../config/database');
const { jwtSecret, jwtExpiresIn, bcryptSaltRounds } = require('../config/auth');
const { UnauthorizedError, ConflictError, ValidationError, ForbiddenError } = require('../utils/errors');
const userRepository = require('../repositories/userRepository');

async function login(req, res, next) {
  try {
    const { email, password } = req.body;
    console.log('[LOGIN DEBUG] email:', JSON.stringify(email), '| password:', JSON.stringify(password), '| length:', password?.length);
    const user = await userRepository.findActiveByEmailWithAdvisory(email);

    if (!user) {
      console.log('[LOGIN DEBUG] User NOT found for email:', email);
      throw new UnauthorizedError('Credenciales invalidas');
    }

    console.log('[LOGIN DEBUG] User found:', user.email, '| hash prefix:', user.password_hash?.substring(0, 20));
    const validPassword = await bcrypt.compare(password, user.password_hash);
    console.log('[LOGIN DEBUG] bcrypt result:', validPassword);
    if (!validPassword) {
      throw new UnauthorizedError('Credenciales invalidas');
    }

    const tokenPayload = {
      id: user.id,
      asesoria_id: user.asesoria_id,
      email: user.email,
      nombre: user.nombre,
      rol: user.rol,
      tipo_usuario: user.tipo_usuario || 'ASESORIA',
    };

    if (user.tipo_usuario === 'EMPRESA' && user.cliente_id) {
      tokenPayload.cliente_id = user.cliente_id;
    }

    const token = jwt.sign(tokenPayload, jwtSecret, { expiresIn: jwtExpiresIn });

    const response = {
      token,
      user: {
        id: user.id,
        email: user.email,
        nombre: user.nombre,
        rol: user.rol,
        tipo_usuario: user.tipo_usuario || 'ASESORIA',
      },
      advisory: {
        id: user.advisory_id,
        nombre: user.advisory_nombre,
        estado: user.advisory_estado,
      },
    };

    if (user.tipo_usuario === 'EMPRESA' && user.cliente_id) {
      response.user.cliente_id = user.cliente_id;
      response.company = {
        id: user.cliente_id,
        nombre: user.cliente_nombre,
        cif: user.cliente_cif,
      };
    }

    res.json(response);
  } catch (err) {
    next(err);
  }
}

async function register(req, res, next) {
  try {
    const { email, password, nombre, rol, tipo_usuario, cliente_id } = req.body;

    const existing = await db.query('SELECT id FROM usuarios WHERE email = $1', [email]);
    if (existing.rows.length > 0) {
      throw new ConflictError('Ya existe un usuario con ese email');
    }

    const passwordHash = await bcrypt.hash(password, bcryptSaltRounds);

    let user;

    if (tipo_usuario === 'EMPRESA') {
      if (!cliente_id) {
        throw new ValidationError('cliente_id es obligatorio para usuarios de empresa');
      }

      // Verify company belongs to the admin's advisory
      const company = await db.query(
        'SELECT id, asesoria_id FROM clientes WHERE id = $1 AND asesoria_id = $2',
        [cliente_id, req.user.asesoria_id]
      );
      if (company.rows.length === 0) {
        throw new ValidationError('La empresa no pertenece a tu asesoria');
      }

      user = await userRepository.createEmpresaUser({
        asesoriaId: req.user.asesoria_id,
        clienteId: cliente_id,
        email,
        passwordHash,
        nombre,
      });
    } else {
      user = await userRepository.createWithinAdvisory({
        asesoriaId: req.user.asesoria_id,
        email,
        passwordHash,
        nombre,
        rol: rol || 'LECTURA',
      });
    }

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

    const response = {
      user: {
        id: user.id,
        email: user.email,
        nombre: user.nombre,
        rol: user.rol,
        tipo_usuario: user.tipo_usuario || 'ASESORIA',
        activo: user.activo,
        created_at: user.created_at,
      },
      advisory: {
        id: user.advisory_id,
        nombre: user.advisory_nombre,
        estado: user.advisory_estado,
      },
    };

    if (user.tipo_usuario === 'EMPRESA' && user.cliente_id) {
      response.user.cliente_id = user.cliente_id;
      response.company = {
        id: user.cliente_id,
        nombre: user.cliente_nombre,
        cif: user.cliente_cif,
      };
    }

    res.json(response);
  } catch (err) {
    next(err);
  }
}

module.exports = { login, register, me };
