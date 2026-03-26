const axios = require('axios');
const aiConfig = require('../config/aiService');

function shouldRetryAiRequest(err) {
  if (!err) {
    return false;
  }

  const message = String(err.message || '').toLowerCase();
  if (err.code === 'ECONNABORTED' || message.includes('timeout')) {
    return false;
  }

  if (err.response) {
    return err.response.status >= 500;
  }

  return true;
}

async function processInvoice(filePath, mimeType, companyContext = {}) {
  const FormData = require('form-data');
  const fs = require('fs');

  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  form.append('mime_type', mimeType);
  form.append('company_name', companyContext.name || '');
  form.append('company_tax_id', companyContext.taxId || '');

  let lastError;
  const attempts = 1 + (aiConfig.retries || 0);

  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const response = await axios.post(`${aiConfig.baseUrl}/ai/process`, form, {
        headers: form.getHeaders(),
        timeout: aiConfig.timeout,
      });
      return response.data;
    } catch (err) {
      lastError = err;
      const canRetry = attempt < attempts && shouldRetryAiRequest(err);

      if (canRetry) {
        const delay = Math.pow(2, attempt - 1) * 1000;
        console.warn(`AI service attempt ${attempt}/${attempts} failed: ${err.message}. Retrying in ${delay}ms...`);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError;
}

async function healthCheck() {
  const response = await axios.get(`${aiConfig.baseUrl}/ai/health`, {
    timeout: 5000,
  });
  return response.data;
}

module.exports = { processInvoice, healthCheck };
