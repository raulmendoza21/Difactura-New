import api from './api';

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password });
  localStorage.setItem('token', data.token);
  localStorage.setItem('user', JSON.stringify(data.user));
  return data;
}

export function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
}

export function getCurrentUser() {
  const userStr = localStorage.getItem('user');
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch {
    return null;
  }
}

export function getToken() {
  return localStorage.getItem('token');
}

export function isAuthenticated() {
  return !!getToken();
}
