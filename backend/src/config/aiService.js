module.exports = {
  baseUrl: process.env.AI_SERVICE_URL || 'http://ai-service:8000',
  timeout: 120000, // 2 minutos para procesamiento de facturas
  retries: 2,
};
