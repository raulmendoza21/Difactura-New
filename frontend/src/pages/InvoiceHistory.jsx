import { useContext, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import InfoPopover from '../components/common/InfoPopover';
import LoadingSpinner from '../components/common/LoadingSpinner';
import StatusPanel from '../components/common/StatusPanel';
import InvoiceTable from '../components/invoices/InvoiceTable';
import { AuthContext } from '../context/AuthContext';
import { useInvoices } from '../hooks/useInvoices';
import { getCompanies } from '../services/companyService';
import { getDashboardStats, reprocessInvoice } from '../services/invoiceService';
import { INVOICE_STATES, INVOICE_STATE_LABELS } from '../utils/constants';

const FILTERS = [
  { key: 'all', label: 'Todo', estado: undefined, accent: 'blue' },
  { key: INVOICE_STATES.SUBIDA, label: 'Subidas', estado: INVOICE_STATES.SUBIDA, accent: 'slate' },
  { key: INVOICE_STATES.EN_PROCESO, label: 'En proceso', estado: INVOICE_STATES.EN_PROCESO, accent: 'blue' },
  { key: INVOICE_STATES.PROCESADA_IA, label: 'Procesadas IA', estado: INVOICE_STATES.PROCESADA_IA, accent: 'indigo' },
  { key: INVOICE_STATES.PENDIENTE_REVISION, label: 'Pendientes', estado: INVOICE_STATES.PENDIENTE_REVISION, accent: 'amber' },
  { key: INVOICE_STATES.ERROR_PROCESAMIENTO, label: 'Con error', estado: INVOICE_STATES.ERROR_PROCESAMIENTO, accent: 'red' },
  { key: INVOICE_STATES.VALIDADA, label: 'Validadas', estado: INVOICE_STATES.VALIDADA, accent: 'emerald' },
  { key: INVOICE_STATES.RECHAZADA, label: 'Rechazadas', estado: INVOICE_STATES.RECHAZADA, accent: 'red' },
];

const CHANNEL_OPTIONS = [
  { value: '', label: 'Todos los canales' },
  { value: 'web', label: 'Web' },
  { value: 'mobile', label: 'Movil' },
  { value: 'camera', label: 'Camara' },
];

const SORT_OPTIONS = [
  { value: 'created_at', label: 'Fecha de entrada' },
  { value: 'fecha_procesado', label: 'Fecha de procesado' },
  { value: 'fecha_factura', label: 'Fecha de factura' },
  { value: 'total', label: 'Total' },
  { value: 'proveedor', label: 'Contraparte' },
  { value: 'cliente', label: 'Empresa asociada' },
  { value: 'fecha_subida', label: 'Fecha de subida' },
];

const DEFAULT_OPERATIONAL_FILTERS = {
  company_id: '',
  channel: '',
  batch_id: '',
  search: '',
  sort_by: 'created_at',
  sort_dir: 'desc',
};

const STATE_FILTER_STYLES = {
  blue: {
    active: 'border-blue-600 bg-blue-600 text-white shadow-blue-200',
    idle: 'border-blue-100 bg-blue-50/70 text-blue-700 hover:border-blue-200 hover:bg-blue-50',
  },
  slate: {
    active: 'border-slate-700 bg-slate-700 text-white shadow-slate-200',
    idle: 'border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300 hover:bg-slate-100',
  },
  indigo: {
    active: 'border-indigo-600 bg-indigo-600 text-white shadow-indigo-200',
    idle: 'border-indigo-100 bg-indigo-50/70 text-indigo-700 hover:border-indigo-200 hover:bg-indigo-50',
  },
  amber: {
    active: 'border-amber-500 bg-amber-500 text-white shadow-amber-200',
    idle: 'border-amber-100 bg-amber-50/80 text-amber-700 hover:border-amber-200 hover:bg-amber-50',
  },
  red: {
    active: 'border-red-500 bg-red-500 text-white shadow-red-200',
    idle: 'border-red-100 bg-red-50/80 text-red-700 hover:border-red-200 hover:bg-red-50',
  },
  emerald: {
    active: 'border-emerald-500 bg-emerald-500 text-white shadow-emerald-200',
    idle: 'border-emerald-100 bg-emerald-50/80 text-emerald-700 hover:border-emerald-200 hover:bg-emerald-50',
  },
};

function buildStatsMap(items = []) {
  return items.reduce((acc, item) => {
    acc[item.estado] = Number(item.count) || 0;
    return acc;
  }, {});
}

function getStateButtonClasses(isActive, accent) {
  const palette = STATE_FILTER_STYLES[accent] || STATE_FILTER_STYLES.slate;
  return isActive ? palette.active : palette.idle;
}

export default function InvoiceHistory() {
  const { advisory, selectedCompany } = useContext(AuthContext);
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [showOperationalFilters, setShowOperationalFilters] = useState(false);
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [actionInvoiceId, setActionInvoiceId] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [operationalFilters, setOperationalFilters] = useState(DEFAULT_OPERATIONAL_FILTERS);
  const { invoices, pagination, loading, error, refetch, updateParams } = useInvoices({
    page: 1,
    limit: 20,
    sort_by: 'created_at',
    sort_dir: 'desc',
  });

  useEffect(() => {
    let cancelled = false;

    const loadCompanies = async () => {
      setCompaniesLoading(true);

      try {
        const data = await getCompanies();
        if (!cancelled) {
          setCompanies(data);
        }
      } catch (err) {
        if (!cancelled) {
          setStatsError(err.response?.data?.message || 'No se pudieron cargar las empresas cliente');
        }
      } finally {
        if (!cancelled) {
          setCompaniesLoading(false);
        }
      }
    };

    loadCompanies();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setOperationalFilters((prev) => ({
      ...prev,
      company_id: selectedCompany?.id ? String(selectedCompany.id) : '',
    }));

    updateParams({
      company_id: selectedCompany?.id ? String(selectedCompany.id) : undefined,
      page: 1,
    });
    setSelectedFilter('all');
    setShowOperationalFilters(false);
  }, [selectedCompany, updateParams]);

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
  }, [refetch, selectedCompany?.id]);

  const countsByState = useMemo(() => buildStatsMap(stats?.por_estado), [stats]);

  const companyById = useMemo(() => {
    return companies.reduce((acc, company) => {
      acc[String(company.id)] = company;
      return acc;
    }, {});
  }, [companies]);

  const appliedOperationalFilters = useMemo(() => {
    const items = [];

    if (operationalFilters.company_id) {
      items.push(
        `Empresa: ${companyById[operationalFilters.company_id]?.nombre || `#${operationalFilters.company_id}`}`
      );
    }
    if (operationalFilters.channel) {
      items.push(
        `Canal: ${
          CHANNEL_OPTIONS.find((option) => option.value === operationalFilters.channel)?.label ||
          operationalFilters.channel
        }`
      );
    }
    if (operationalFilters.batch_id.trim()) {
      items.push(`Lote: ${operationalFilters.batch_id.trim()}`);
    }
    if (operationalFilters.search.trim()) {
      items.push(`Busqueda: ${operationalFilters.search.trim()}`);
    }

    return items;
  }, [companyById, operationalFilters]);

  const hasManualOperationalFilters =
    (!selectedCompany && Boolean(operationalFilters.company_id)) ||
    Boolean(operationalFilters.channel) ||
    Boolean(operationalFilters.batch_id.trim()) ||
    Boolean(operationalFilters.search.trim()) ||
    operationalFilters.sort_by !== DEFAULT_OPERATIONAL_FILTERS.sort_by ||
    operationalFilters.sort_dir !== DEFAULT_OPERATIONAL_FILTERS.sort_dir;

  const activeFilter = FILTERS.find((item) => item.key === selectedFilter);
  const totalPages = Math.ceil(pagination.total / pagination.limit) || 1;

  const handleFilter = (filterKey) => {
    setSelectedFilter(filterKey);
    const filter = FILTERS.find((item) => item.key === filterKey);
    updateParams({ estado: filter?.estado, page: 1 });
  };

  const handleOperationalFilterChange = (field, value) => {
    setOperationalFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleApplyOperationalFilters = (event) => {
    event.preventDefault();

    updateParams({
      company_id: operationalFilters.company_id || undefined,
      channel: operationalFilters.channel || undefined,
      batch_id: operationalFilters.batch_id.trim() || undefined,
      search: operationalFilters.search.trim() || undefined,
      sort_by: operationalFilters.sort_by,
      sort_dir: operationalFilters.sort_dir,
      page: 1,
    });

    setShowOperationalFilters(false);
  };

  const handleClearOperationalFilters = () => {
    const nextCompanyId = selectedCompany?.id ? String(selectedCompany.id) : '';

    setSelectedFilter('all');
    setOperationalFilters({
      ...DEFAULT_OPERATIONAL_FILTERS,
      company_id: nextCompanyId,
    });
    setFeedback('');
    updateParams({
      estado: undefined,
      company_id: nextCompanyId || undefined,
      channel: undefined,
      batch_id: undefined,
      search: undefined,
      sort_by: DEFAULT_OPERATIONAL_FILTERS.sort_by,
      sort_dir: DEFAULT_OPERATIONAL_FILTERS.sort_dir,
      page: 1,
    });
    setShowOperationalFilters(false);
  };

  const handleRefresh = async () => {
    setFeedback('');
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

  const handleReprocess = async (invoice) => {
    setActionInvoiceId(invoice.id);
    setFeedback('');
    setStatsError('');

    try {
      await reprocessInvoice(invoice.id);
      setFeedback(`La factura ${invoice.documento_json?.numero_factura || `#${invoice.id}`} ha vuelto a la cola de procesamiento.`);
      await handleRefresh();
    } catch (err) {
      setStatsError(err.response?.data?.message || 'No se pudo relanzar el procesamiento');
    } finally {
      setActionInvoiceId(null);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
            Operativa documental
          </p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Bandeja documental</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Aqui puedes ver las facturas de la empresa activa, con su estado de cola, revision y
            validacion.
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

      {(statsError || error) && (
        <StatusPanel
          tone="warning"
          eyebrow="Sincronizacion"
          title="No se pudo actualizar toda la bandeja"
          description={statsError || error}
          compact
        />
      )}

      {feedback && (
        <StatusPanel
          tone="success"
          eyebrow="Accion completada"
          title="La bandeja se ha actualizado"
          description={feedback}
          compact
        />
      )}

      {!selectedCompany && (
        <StatusPanel
          tone="warning"
          eyebrow="Empresa activa"
          title="Estas viendo la bandeja global de la asesoria"
          description="Selecciona una empresa desde la barra superior para trabajar con una vista acotada."
          compact
        />
      )}

      <section className="relative isolate rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-5">
          <div className="relative z-20 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                  Panel de trabajo
                </p>
                <InfoPopover
                  title="Panel de trabajo"
                  description="Concentra el filtrado por estado, los filtros avanzados y la tabla documental en un mismo bloque."
                  items={[
                    'Usa las tarjetas pequenas para alternar rapido entre estados.',
                    'Abre el panel Filtrar solo cuando necesites afinar por empresa, canal, lote o texto.',
                  ]}
                  placement="right"
                  widthClass="w-80"
                />
              </div>
              <h2 className="mt-2 text-xl font-semibold text-slate-900">Documentos en bandeja</h2>
              <p className="mt-2 text-sm text-slate-500">
                {selectedCompany
                  ? `Trabajando sobre ${selectedCompany.nombre}.`
                  : 'Vista global de la asesoria con todos los documentos disponibles.'}
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {hasManualOperationalFilters && (
                <button type="button" onClick={handleClearOperationalFilters} className="btn-secondary">
                  Limpiar
                </button>
              )}
              <button
                type="button"
                onClick={() => setShowOperationalFilters((current) => !current)}
                className="btn-secondary"
              >
                {showOperationalFilters ? 'Ocultar filtros' : 'Filtrar'}
              </button>
            </div>
          </div>

          <div className="relative z-0 grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-8">
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
                  className={`relative z-0 rounded-2xl border p-4 text-left transition-all duration-200 ${getStateButtonClasses(
                    isActive,
                    filter.accent
                  )} ${isActive ? 'shadow-md' : 'shadow-sm'}`}
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] opacity-80">
                    {filter.label}
                  </p>
                  <p className="mt-3 text-2xl font-bold">{count}</p>
                </button>
              );
            })}
          </div>

          {appliedOperationalFilters.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {appliedOperationalFilters.map((item) => (
                <span
                  key={item}
                  className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600"
                >
                  {item}
                </span>
              ))}
            </div>
          )}

          {showOperationalFilters && (
            <form
              onSubmit={handleApplyOperationalFilters}
              className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4"
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <label className="space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Buscar
                  </span>
                  <input
                    className="input-field"
                    placeholder="Numero, contraparte, empresa asociada, archivo..."
                    value={operationalFilters.search}
                    onChange={(event) => handleOperationalFilterChange('search', event.target.value)}
                  />
                </label>

                <label className="space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Empresa asociada
                  </span>
                  <select
                    className="input-field"
                    value={operationalFilters.company_id}
                    onChange={(event) => handleOperationalFilterChange('company_id', event.target.value)}
                    disabled={companiesLoading || !!selectedCompany}
                  >
                    <option value="">Todas las empresas</option>
                    {companies.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.nombre}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Canal
                  </span>
                  <select
                    className="input-field"
                    value={operationalFilters.channel}
                    onChange={(event) => handleOperationalFilterChange('channel', event.target.value)}
                  >
                    {CHANNEL_OPTIONS.map((option) => (
                      <option key={option.value || 'all'} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Lote
                  </span>
                  <input
                    className="input-field"
                    placeholder="upl_2026..."
                    value={operationalFilters.batch_id}
                    onChange={(event) => handleOperationalFilterChange('batch_id', event.target.value)}
                  />
                </label>

                <label className="space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Orden
                  </span>
                  <select
                    className="input-field"
                    value={operationalFilters.sort_by}
                    onChange={(event) => handleOperationalFilterChange('sort_by', event.target.value)}
                  >
                    {SORT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Direccion
                  </span>
                  <select
                    className="input-field"
                    value={operationalFilters.sort_dir}
                    onChange={(event) => handleOperationalFilterChange('sort_dir', event.target.value)}
                  >
                    <option value="desc">Mas reciente primero</option>
                    <option value="asc">Mas antiguo primero</option>
                  </select>
                </label>
              </div>

              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowOperationalFilters(false)}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button type="submit" className="btn-primary">
                  Aplicar filtros
                </button>
              </div>
            </form>
          )}

          <div className="rounded-2xl border border-slate-100 bg-slate-50/70 px-4 py-3">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <p className="text-sm text-slate-600">
                {pagination.total} documento{pagination.total !== 1 ? 's' : ''}{' '}
                {activeFilter?.estado
                  ? `en estado ${INVOICE_STATE_LABELS[activeFilter.estado] || activeFilter.estado}`
                  : 'visibles en la bandeja'}
              </p>
              <p className="text-xs text-slate-400">
                {appliedOperationalFilters.length > 0
                  ? `Filtros activos: ${appliedOperationalFilters.join(' · ')}`
                  : 'Sin filtros operativos activos'}
              </p>
            </div>
          </div>

          {loading ? (
            <LoadingSpinner text="Cargando bandeja documental..." />
          ) : (
            <>
              <InvoiceTable
                invoices={invoices}
                scrollable
                onReprocess={handleReprocess}
                actionInvoiceId={actionInvoiceId}
              />

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
        </div>
      </section>

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
