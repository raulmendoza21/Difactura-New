import { useState, useEffect, useCallback } from 'react';
import * as invoiceService from '../services/invoiceService';

export function useInvoices(initialParams = {}) {
  const [invoices, setInvoices] = useState([]);
  const [pagination, setPagination] = useState({ total: 0, page: 1, limit: 20 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchInvoices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await invoiceService.getInvoices(params);
      setInvoices(data.facturas || []);
      setPagination(data.pagination || { total: 0, page: 1, limit: 20 });
    } catch (err) {
      setError(err.response?.data?.message || 'Error al cargar facturas');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  const updateParams = (newParams) => {
    setParams((prev) => ({ ...prev, ...newParams }));
  };

  return { invoices, pagination, loading, error, refetch: fetchInvoices, updateParams };
}
