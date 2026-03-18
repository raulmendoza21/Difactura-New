import api from './api';

const STORAGE_KEYS = {
  token: 'token',
  user: 'user',
  advisory: 'advisory',
  selectedCompany: 'selectedCompany',
};

function readJson(key) {
  const value = localStorage.getItem(key);
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function writeJson(key, value) {
  if (!value) {
    localStorage.removeItem(key);
    return;
  }

  localStorage.setItem(key, JSON.stringify(value));
}

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password });
  localStorage.setItem(STORAGE_KEYS.token, data.token);
  writeJson(STORAGE_KEYS.user, data.user);
  writeJson(STORAGE_KEYS.advisory, data.advisory);
  localStorage.removeItem(STORAGE_KEYS.selectedCompany);
  return data;
}

export function logout() {
  localStorage.removeItem(STORAGE_KEYS.token);
  localStorage.removeItem(STORAGE_KEYS.user);
  localStorage.removeItem(STORAGE_KEYS.advisory);
  localStorage.removeItem(STORAGE_KEYS.selectedCompany);
}

export function getCurrentUser() {
  return readJson(STORAGE_KEYS.user);
}

export function getCurrentAdvisory() {
  return readJson(STORAGE_KEYS.advisory);
}

export function getSelectedCompany() {
  return readJson(STORAGE_KEYS.selectedCompany);
}

export function setSelectedCompany(company) {
  writeJson(STORAGE_KEYS.selectedCompany, company);
}

export function clearSelectedCompany() {
  localStorage.removeItem(STORAGE_KEYS.selectedCompany);
}

export function getToken() {
  return localStorage.getItem(STORAGE_KEYS.token);
}

export function isAuthenticated() {
  return !!getToken();
}
