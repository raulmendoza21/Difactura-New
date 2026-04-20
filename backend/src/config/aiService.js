function parseIntegerEnv(name, defaultValue) {
  const rawValue = process.env[name];
  const parsedValue = Number.parseInt(rawValue ?? '', 10);
  return Number.isFinite(parsedValue) ? parsedValue : defaultValue;
}

function parseAdditionalTaxIds(raw) {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.map(String).filter(Boolean);
  } catch { /* ignore */ }
  return raw.split(',').map(s => s.trim()).filter(Boolean);
}

module.exports = {
  baseUrl: process.env.AI_SERVICE_URL || 'http://ai-service-vision:8001',
  timeout: parseIntegerEnv('AI_SERVICE_TIMEOUT_MS', 300000),
  retries: parseIntegerEnv('AI_SERVICE_RETRIES', 0),
  additionalTaxIds: parseAdditionalTaxIds(process.env.COMPANY_ADDITIONAL_TAX_IDS),
};
