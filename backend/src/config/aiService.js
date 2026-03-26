function parseIntegerEnv(name, defaultValue) {
  const rawValue = process.env[name];
  const parsedValue = Number.parseInt(rawValue ?? '', 10);
  return Number.isFinite(parsedValue) ? parsedValue : defaultValue;
}

module.exports = {
  baseUrl: process.env.AI_SERVICE_URL || 'http://ai-service:8000',
  timeout: parseIntegerEnv('AI_SERVICE_TIMEOUT_MS', 300000),
  retries: parseIntegerEnv('AI_SERVICE_RETRIES', 0),
};
