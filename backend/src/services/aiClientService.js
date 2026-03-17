const axios = require('axios');
const aiConfig = require('../config/aiService');

async function processInvoice(filePath, mimeType) {
  const FormData = require('form-data');
  const fs = require('fs');

  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  form.append('mime_type', mimeType);

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
      if (attempt < attempts) {
        const delay = Math.pow(2, attempt - 1) * 1000;
        console.warn(`AI service attempt ${attempt}/${attempts} failed: ${err.message}. Retrying in ${delay}ms…`);
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
