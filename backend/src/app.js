const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const requestLogger = require('./middleware/requestLogger');
const errorHandler = require('./middleware/errorHandler');
const routes = require('./routes');
const db = require('./config/database');

const app = express();

// Seguridad y parsing
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(requestLogger);

// Health check
app.get('/api/health', async (req, res) => {
  try {
    const dbTime = await db.testConnection();
    res.json({ status: 'ok', db: 'connected', timestamp: dbTime });
  } catch (err) {
    res.status(503).json({ status: 'error', db: 'disconnected', message: err.message });
  }
});

// Rutas de la API
app.use('/api', routes);

// Error handler (siempre al final)
app.use(errorHandler);

module.exports = app;
