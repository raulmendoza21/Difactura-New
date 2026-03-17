module.exports = {
  jwtSecret: process.env.JWT_SECRET || 'dev-secret-cambiar-en-produccion',
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || '8h',
  bcryptSaltRounds: parseInt(process.env.BCRYPT_SALT_ROUNDS || '12', 10),
};
