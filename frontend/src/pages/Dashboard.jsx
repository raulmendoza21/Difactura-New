import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/common/LoadingSpinner';
import StatusPanel from '../components/common/StatusPanel';
import CompanySelector from '../components/companies/CompanySelector';
import Charts from '../components/dashboard/Charts';
import RecentActivity from '../components/dashboard/RecentActivity';
import StatsCard from '../components/dashboard/StatsCard';
import { useAuth } from '../hooks/useAuth';
import { getCompanies } from '../services/companyService';
import { getDashboardStats } from '../services/invoiceService';

function buildStatsMap(items = []) {
  return items.reduce((acc, item) => {
    acc[item.estado] = Number(item.count) || 0;
    return acc;
  }, {});
}

export default function Dashboard() {
  const { advisory, selectedCompany, setSelectedCompany, clearSelectedCompany } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error, setError] = useState('');
  const [statsError, setStatsError] = useState('');

  useEffect(() => {
    let active = true;

    const loadCompanies = async () => {
      try {
        const items = await getCompanies();
        if (!active) return;
        setCompanies(items);
        setError('');
      } catch (err) {
        if (!active) return;
        setError(err.response?.data?.message || 'No se pudieron cargar las empresas cliente.');
      } finally {
        if (!active) return;
        setLoading(false);
      }
    };

    const loadStats = async () => {
      try {
        const nextStats = await getDashboardStats();
        if (!active) return;
        setStats(nextStats);
        setStatsError('');
      } catch (err) {
        if (!active) return;
        setStatsError(err.response?.data?.message || 'No se pudo cargar el resumen operativo.');
      } finally {
        if (!active) return;
        setStatsLoading(false);
      }
    };

    loadCompanies();
    loadStats();

    const interval = setInterval(loadStats, 15000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (loading || companies.length === 0 || !selectedCompany) {
      return;
    }

    const exists = companies.some((company) => company.id === selectedCompany.id);
    if (!exists) {
      clearSelectedCompany();
    }
  }, [loading, companies, selectedCompany, clearSelectedCompany]);

  const selectedCompanyDetails =
    companies.find((company) => company.id === selectedCompany?.id) || selectedCompany;

  const statsByState = useMemo(() => buildStatsMap(stats?.por_estado), [stats]);

  const handleCompanyChange = (event) => {
    const companyId = Number(event.target.value);

    if (!companyId) {
      clearSelectedCompany();
      return;
    }

    const company = companies.find((item) => item.id === companyId);
    if (company) {
      setSelectedCompany(company);
    }
  };

  if (loading) {
    return <LoadingSpinner text="Cargando centro operativo..." />;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="relative overflow-hidden rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-blue-100/70 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-32 w-32 rounded-full bg-emerald-100/60 blur-3xl" />

        <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              Operativa de asesoria
            </p>
            <h1 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">
              Centro operativo documental
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
              Desde aqui preparas el contexto de trabajo, controlas la carga documental de la asesoria
              y saltas rapido a la subida o a la bandeja de revision.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[360px]">
            <Link to="/invoices/upload" className="btn-primary justify-center text-center">
              Subir documentos
            </Link>
            <Link to="/invoices" className="btn-secondary justify-center text-center">
              Abrir bandeja documental
            </Link>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          title="Empresas cliente"
          value={companies.length}
          subtitle="Empresas dadas de alta para esta asesoria"
          color="blue"
          icon="M17 20h5V4H2v16h5m10 0v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6m10 0H7"
        />
        <StatsCard
          title="Pendientes"
          value={stats?.pendientes_revision ?? 0}
          subtitle="Documentos listos para revision humana"
          color="amber"
          icon="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
        <StatsCard
          title="Validadas"
          value={stats?.validadas ?? 0}
          subtitle="Facturas ya confirmadas"
          color="emerald"
          icon="M5 13l4 4L19 7"
        />
        <StatsCard
          title="Con error"
          value={stats?.errores ?? 0}
          subtitle="Necesitan reproceso o revision manual"
          color="red"
          icon="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </div>

      {(error || statsError) && (
        <StatusPanel
          tone="warning"
          eyebrow="Sincronizacion"
          title="La portada no esta completamente actualizada"
          description={error || statsError}
          compact
        />
      )}

      {!selectedCompanyDetails && (
        <StatusPanel
          tone="warning"
          eyebrow="Seleccion requerida"
          title="Elige una empresa cliente para empezar"
          description="La subida documental y parte del flujo operativo usan la empresa activa como contexto."
          items={[
            'Selecciona la empresa con la que vas a trabajar ahora.',
            'Ese contexto se reutiliza en la subida y en la revision documental.',
          ]}
          compact
        />
      )}

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <CompanySelector
          companies={companies}
          value={selectedCompany?.id || ''}
          onChange={handleCompanyChange}
          loading={loading}
        />

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            Contexto activo
          </p>

          <div className="mt-4 grid gap-4">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Asesoria</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">
                {advisory?.nombre || 'Sin asesoria'}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                Tu trabajo y la bandeja documental se ejecutan dentro de este contexto.
              </p>
            </div>

            <div className={`rounded-2xl p-4 ${selectedCompanyDetails ? 'bg-emerald-50' : 'bg-amber-50'}`}>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Empresa activa</p>
              {selectedCompanyDetails ? (
                <>
                  <p className="mt-2 text-lg font-semibold text-slate-900">{selectedCompanyDetails.nombre}</p>
                  <p className="mt-1 text-sm text-slate-600">
                    {selectedCompanyDetails.cif || 'Sin CIF registrado'}
                  </p>
                  <p className="mt-3 text-sm text-slate-500">
                    Los nuevos documentos que subas se asociaran por defecto a esta empresa cliente.
                  </p>
                </>
              ) : (
                <>
                  <p className="mt-2 text-lg font-semibold text-slate-900">Ninguna seleccionada</p>
                  <p className="mt-3 text-sm text-slate-500">
                    Deja una empresa seleccionada para trabajar mas rapido en la recepcion documental.
                  </p>
                </>
              )}
            </div>

            <div className="rounded-2xl border border-slate-100 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Siguiente accion recomendada</p>
              <p className="mt-2 text-sm text-slate-600">
                {selectedCompanyDetails
                  ? `Puedes subir un nuevo lote para ${selectedCompanyDetails.nombre} o revisar la bandeja documental.`
                  : 'Selecciona primero una empresa cliente y luego empieza a subir documentos.'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
              Acciones rapidas
            </p>
            <div className="mt-4 grid gap-3">
              <Link
                to="/invoices/upload"
                className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-700 transition-colors hover:border-blue-200 hover:bg-blue-50"
              >
                <div>
                  <p className="font-semibold text-slate-900">Recibir un nuevo lote</p>
                  <p className="mt-1 text-xs text-slate-500">Sube PDFs, imagenes o fotos desde movil.</p>
                </div>
                <span className="text-blue-600">Abrir</span>
              </Link>

              <Link
                to="/invoices"
                className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-700 transition-colors hover:border-blue-200 hover:bg-blue-50"
              >
                <div>
                  <p className="font-semibold text-slate-900">Revisar bandeja documental</p>
                  <p className="mt-1 text-xs text-slate-500">Controla subidas, pendientes, errores y validadas.</p>
                </div>
                <span className="text-blue-600">Abrir</span>
              </Link>
            </div>
          </div>

          <Charts statsByState={statsByState} />
        </div>

        <RecentActivity activities={stats?.actividad_reciente || []} loading={statsLoading} />
      </div>
    </div>
  );
}
