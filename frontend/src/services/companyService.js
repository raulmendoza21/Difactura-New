import api from './api';

export async function getCompanies() {
  const { data } = await api.get('/companies');
  return data.data || [];
}

export async function getCompanyById(id) {
  const { data } = await api.get(`/companies/${id}`);
  return data.data || null;
}
