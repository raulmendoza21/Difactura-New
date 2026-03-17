import api from './api';

export async function uploadInvoice(file) {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post('/invoices/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  return data;
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

export async function getDashboardStats() {
  const { data } = await api.get('/dashboard');
  return data;
}
