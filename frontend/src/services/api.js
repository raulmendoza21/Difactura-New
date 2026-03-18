import axios from 'axios';

function getStoredCompanyId() {
  const raw = localStorage.getItem('selectedCompany');
  if (!raw) {
    return null;
  }

  try {
    const company = JSON.parse(raw);
    return company?.id || null;
  } catch {
    return null;
  }
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  const companyId = getStoredCompanyId();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  if (companyId) {
    config.headers['X-Company-Id'] = String(companyId);
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      localStorage.removeItem('advisory');
      localStorage.removeItem('selectedCompany');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
