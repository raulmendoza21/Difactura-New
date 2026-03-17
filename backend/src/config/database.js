const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

pool.on('error', (err) => {
  console.error('Error inesperado en el pool de PostgreSQL:', err);
});

async function query(text, params) {
  return pool.query(text, params);
}

async function getClient() {
  return pool.connect();
}

async function testConnection() {
  const result = await pool.query('SELECT NOW()');
  return result.rows[0].now;
}

module.exports = { pool, query, getClient, testConnection };
