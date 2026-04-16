import api from './api';

export async function uploadInvoices(files, { companyId, channel = 'web', onProgress } = {}) {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  if (companyId) {
    formData.append('company_id', String(companyId));
  }
  formData.append('channel', channel);

  const { data } = await api.post('/invoices/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: onProgress
      ? (e) => onProgress(e.total ? Math.round((e.loaded * 100) / e.total) : 0)
      : undefined,
  });
  return data;
}

export async function uploadInvoice(file, options = {}) {
  return uploadInvoices([file], options);
}

export async function getInvoices(params = {}) {
  const { data } = await api.get('/invoices', { params });
  return data;
}

export async function getInvoiceById(id) {
  const { data } = await api.get(`/invoices/${id}`);
  return data;
}

export async function updateInvoice(id, updates) {
  const { data } = await api.put(`/invoices/${id}`, updates);
  return data;
}

export async function validateInvoice(id) {
  const { data } = await api.post(`/invoices/${id}/validate`);
  return data;
}

export async function rejectInvoice(id, motivo) {
  const { data } = await api.post(`/invoices/${id}/reject`, { motivo });
  return data;
}

export async function reprocessInvoice(id) {
  const { data } = await api.post(`/invoices/${id}/reprocess`);
  return data;
}

export async function getDashboardStats() {
  const { data } = await api.get('/dashboard');
  return data;
}
