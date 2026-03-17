import { useState } from 'react';
import InvoiceTable from '../components/invoices/InvoiceTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useInvoices } from '../hooks/useInvoices';
import { useDebounce } from '../hooks/useDebounce';
import { INVOICE_STATES } from '../utils/constants';

export default function InvoiceHistory() {
  const [search, setSearch] = useState('');
  const [estado, setEstado] = useState('');
  const debouncedSearch = useDebounce(search, 400);
  const { invoices, pagination, loading, updateParams } = useInvoices({ page: 1, limit: 20 });

  const handleSearch = (val) => {
    setSearch(val);
    updateParams({ search: val, page: 1 });
  };

  const handleFilter = (val) => {
    setEstado(val);
    updateParams({ estado: val || undefined, page: 1 });
  };

  const handlePage = (newPage) => {
    updateParams({ page: newPage });
  };

  const totalPages = Math.ceil(pagination.total / pagination.limit) || 1;

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Historial de facturas</h1>
        <p className="text-sm text-slate-500 mt-1">{pagination.total} factura{pagination.total !== 1 ? 's' : ''} en total</p>
      </div>

      {/* Filtros */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1 relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input
            type="text"
            placeholder="Buscar por número, proveedor..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="input-field pl-10"
          />
        </div>
        <select
          value={estado}
          onChange={(e) => handleFilter(e.target.value)}
          className="input-field sm:w-48"
        >
          <option value="">Todos los estados</option>
          {Object.entries(INVOICE_STATES).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {loading ? <LoadingSpinner /> : <InvoiceTable invoices={invoices} />}

      {/* Paginación */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => handlePage(pagination.page - 1)}
            disabled={pagination.page <= 1}
            className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-30"
          >
            Anterior
          </button>
          <span className="text-sm text-slate-500">
            Página {pagination.page} de {totalPages}
          </span>
          <button
            onClick={() => handlePage(pagination.page + 1)}
            disabled={pagination.page >= totalPages}
            className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-30"
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  );
}
