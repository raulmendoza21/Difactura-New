import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/common/LoadingSpinner';
import StatusPanel from '../components/common/StatusPanel';
import StatsCard from '../components/dashboard/StatsCard';
import InvoiceTable from '../components/invoices/InvoiceTable';
import { useInvoices } from '../hooks/useInvoices';
import { getDashboardStats } from '../services/invoiceService';
import { INVOICE_STATES, INVOICE_STATE_LABELS } from '../utils/constants';

const FILTERS = [
  { key: 'all', label: 'Todo', estado: undefined },
  { key: INVOICE_STATES.SUBIDA, label: 'Subidas', estado: INVOICE_STATES.SUBIDA },
  { key: INVOICE_STATES.EN_PROCESO, label: 'En proceso', estado: INVOICE_STATES.EN_PROCESO },
  { key: INVOICE_STATES.PENDIENTE_REVISION, label: 'Pendientes', estado: INVOICE_STATES.PENDIENTE_REVISION },
  { key: INVOICE_STATES.ERROR_PROCESAMIENTO, label: 'Con error', estado: INVOICE_STATES.ERROR_PROCESAMIENTO },
  { key: INVOICE_STATES.VALIDADA, label: 'Validadas', estado: INVOICE_STATES.VALIDADA },
];

export default function InvoiceHistory() {
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState('');
  const {
    invoices,
    pagination,
    loading,
    error,
    refetch,
    updateParams,
  } = useInvoices({ page: 1, limit: 20 });

  useEffect(() => {
    let cancelled = false;

    const loadStats = async () => {
      setStatsLoading(true);

      try {
        const nextStats = await getDashboardStats();
        if (!cancelled) {
          setStats(nextStats);
          setStatsError('');
        }
      } catch (err) {
        if (!cancelled) {
          setStatsError(err.response?.data?.message || 'No se pudieron cargar las metricas');
        }
      } finally {
        if (!cancelled) {
          setStatsLoading(false);
        }
      }
    };

    const syncBoard = async () => {
      await Promise.allSettled([loadStats(), refetch()]);
    };

    syncBoard();
    const interval = setInterval(syncBoard, 10000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [refetch]);

  const countsByState = useMemo(() => {
    const source = stats?.por_estado || [];
    return source.reduce((acc, item) => {
      acc[item.estado] = Number(item.count) || 0;
      return acc;
    }, {});
  }, [stats]);

  const handleFilter = (filterKey) => {
    setSelectedFilter(filterKey);
    const filter = FILTERS.find((item) => item.key === filterKey);
    updateParams({ estado: filter?.estado, page: 1 });
  };

  const handleRefresh = async () => {
    setStatsLoading(true);

    try {
      const nextStats = await getDashboardStats();
      setStats(nextStats);
      setStatsError('');
    } catch (err) {
      setStatsError(err.response?.data?.message || 'No se pudieron cargar las metricas');
    } finally {
      setStatsLoading(false);
    }

    await refetch();
  };

  const handlePage = (newPage) => {
    updateParams({ page: newPage });
  };

  const totalPages = Math.ceil(pagination.total / pagination.limit) || 1;
  const activeFilter = FILTERS.find((item) => item.key === selectedFilter);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
            Operativa documental
          </p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Bandeja documental</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Aqui puedes ver todas las facturas que han entrado en la asesoria: subidas, en proceso,
            pendientes de revision, con error o ya validadas.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button onClick={handleRefresh} className="btn-secondary" disabled={loading || statsLoading}>
            {loading || statsLoading ? 'Actualizando...' : 'Actualizar bandeja'}
          </button>
          <Link to="/invoices/upload" className="btn-primary">
            Subir documentos
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          title="Total documentos"
          value={stats?.total ?? 0}
          subtitle="Documentos registrados en la asesoria"
          color="blue"
          icon="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
        <StatsCard
          title="Pendientes"
          value={stats?.pendientes_revision ?? 0}
          subtitle="Listas para revisar por la asesoria"
          color="amber"
          icon="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
        <StatsCard
          title="Validadas"
          value={stats?.validadas ?? 0}
          subtitle="Facturas confirmadas manualmente"
          color="emerald"
          icon="M5 13l4 4L19 7"
        />
        <StatsCard
          title="Con error"
          value={stats?.errores ?? 0}
          subtitle="Necesitan reproceso o revision"
          color="red"
          icon="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </div>

      {(statsError || error) && (
        <StatusPanel
          tone="warning"
          eyebrow="Sincronizacion"
          title="No se pudo actualizar toda la bandeja"
          description={statsError || error}
          compact
        />
      )}

      <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <p className="text-sm text-slate-600">
          Filtra por estado para priorizar el trabajo y abre cada factura directamente desde la tabla.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((filter) => {
          const isActive = selectedFilter === filter.key;
          const count =
            filter.key === 'all'
              ? stats?.total ?? pagination.total
              : countsByState[filter.estado] ?? 0;

          return (
            <button
              key={filter.key}
              type="button"
              onClick={() => handleFilter(filter.key)}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'border-blue-600 bg-blue-600 text-white shadow-sm'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900'
              }`}
            >
              {filter.label} ({count})
            </button>
          );
        })}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <p className="text-sm text-slate-500">
          {pagination.total} documento{pagination.total !== 1 ? 's' : ''}{' '}
          {activeFilter?.estado
            ? `en estado ${INVOICE_STATE_LABELS[activeFilter.estado] || activeFilter.estado}`
            : 'visibles en la bandeja'}
        </p>
      </div>

      {loading ? (
        <LoadingSpinner text="Cargando bandeja documental..." />
      ) : (
        <>
          <InvoiceTable invoices={invoices} scrollable />

          {invoices.length === 0 && (
            <StatusPanel
              tone="success"
              eyebrow="Sin resultados"
              title="No hay documentos en este filtro"
              description="Prueba otro estado o espera a que entren nuevos documentos en la asesoria."
              compact
            />
          )}
        </>
      )}

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
            Pagina {pagination.page} de {totalPages}
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
