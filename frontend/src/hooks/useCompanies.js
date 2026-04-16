import { useEffect, useState } from 'react';
import { getCompanies } from '../services/companyService';

let cachedCompanies = null;
let fetchPromise = null;

function fetchCompanies() {
  if (cachedCompanies) return Promise.resolve(cachedCompanies);
  if (fetchPromise) return fetchPromise;

  fetchPromise = getCompanies()
    .then((data) => {
      cachedCompanies = data;
      fetchPromise = null;
      return data;
    })
    .catch((err) => {
      fetchPromise = null;
      throw err;
    });

  return fetchPromise;
}

export function invalidateCompaniesCache() {
  cachedCompanies = null;
  fetchPromise = null;
}

export function useCompanies() {
  const [companies, setCompanies] = useState(cachedCompanies || []);
  const [loading, setLoading] = useState(!cachedCompanies);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    fetchCompanies()
      .then((data) => {
        if (!active) return;
        setCompanies(data);
        setError('');
      })
      .catch((err) => {
        if (!active) return;
        setError(err.response?.data?.message || 'No se pudieron cargar las empresas cliente');
        setCompanies([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return { companies, loading, error };
}
