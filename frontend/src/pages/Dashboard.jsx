import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/common/LoadingSpinner';
import InfoPopover from '../components/common/InfoPopover';
import StatusPanel from '../components/common/StatusPanel';
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
  const { advisory, selectedCompany, clearSelectedCompany } = useAuth();
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

    loadCompanies();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

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

    setStatsLoading(true);
    loadStats();

    const interval = setInterval(loadStats, 15000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [selectedCompany?.id]);

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
              Controla la carga documental, revisa el contexto activo y entra rapido en la subida o
              en la bandeja de trabajo.
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
          title={selectedCompanyDetails ? 'Docs empresa activa' : 'Empresas cliente'}
          value={selectedCompanyDetails ? stats?.total ?? 0 : companies.length}
          subtitle={
            selectedCompanyDetails
              ? 'Documentos visibles para la empresa seleccionada'
              : 'Empresas dadas de alta para esta asesoria'
          }
          color="blue"
          icon="M17 20h5V4H2v16h5m10 0v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6m10 0H7"
          infoTitle={selectedCompanyDetails ? 'Documentos empresa activa' : 'Empresas cliente'}
          infoDescription={
            selectedCompanyDetails
              ? 'Cuenta el volumen documental visible para la empresa que has seleccionado arriba.'
              : 'Cuenta las empresas cliente dadas de alta en la asesoria.'
          }
          infoItems={
            selectedCompanyDetails
              ? [
                  'Este numero cambia automaticamente cuando cambias de empresa activa.',
                  'Incluye documentos pendientes, en proceso, con error y validados.',
                ]
              : ['Si eliges una empresa en la barra superior, el centro operativo se acota a ella.']
          }
        />
        <StatsCard
          title="Pendientes"
          value={stats?.pendientes_revision ?? 0}
          subtitle={
            selectedCompanyDetails
              ? 'Pendientes de la empresa activa'
              : 'Documentos listos para revision'
          }
          color="amber"
          icon="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          infoTitle="Pendientes"
          infoDescription="Documentos ya procesados que esperan revision antes de confirmarse."
          infoItems={[
            'Son el bloque principal de trabajo para la asesoria.',
            'No quedan validados hasta que alguien revise y confirme la factura.',
          ]}
        />
        <StatsCard
          title="Validadas"
          value={stats?.validadas ?? 0}
          subtitle={
            selectedCompanyDetails
              ? 'Validadas para la empresa activa'
              : 'Facturas ya confirmadas'
          }
          color="emerald"
          icon="M5 13l4 4L19 7"
          infoTitle="Validadas"
          infoDescription="Facturas ya revisadas y confirmadas por una persona del equipo."
          infoItems={['Este bloque ayuda a ver el avance real del trabajo cerrado.']}
        />
        <StatsCard
          title="Con error"
          value={stats?.errores ?? 0}
          subtitle={
            selectedCompanyDetails
              ? 'Errores de la empresa activa'
              : 'Necesitan reproceso o revision'
          }
          color="red"
          icon="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          infoTitle="Con error"
          infoDescription="Documentos que no han completado correctamente el flujo automatico."
          infoItems={['Conviene revisarlos o lanzarlos de nuevo a la cola.']}
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
          title="Elige una empresa cliente desde la barra superior"
          description="La empresa activa acota la bandeja, las metricas y el contexto de subida."
          items={[
            'Si seleccionas una empresa, todo el trabajo operativo se filtra por ella.',
            'Si no seleccionas ninguna, veras el agregado global de la asesoria.',
          ]}
          compact
        />
      )}

      <div className="grid gap-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
              Contexto activo
            </p>
            <InfoPopover
              title="Contexto activo"
              description="Resume desde que asesoria y empresa estas operando ahora mismo."
              items={[
                'La empresa activa filtra bandeja, metricas y nuevas subidas.',
                'Si no hay empresa activa, veras la vista global de la asesoria.',
              ]}
              align="left"
            />
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Asesoria</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">
                {advisory?.nombre || 'Sin asesoria'}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                Todo el trabajo se ejecuta dentro de este contexto.
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
                    La bandeja y las metricas se estan filtrando por esta empresa.
                  </p>
                </>
              ) : (
                <>
                  <p className="mt-2 text-lg font-semibold text-slate-900">Vista global</p>
                  <p className="mt-3 text-sm text-slate-500">
                    Selecciona una empresa arriba para trabajar en modo acotado.
                  </p>
                </>
              )}
            </div>

            <div className="rounded-2xl border border-slate-100 bg-white p-4">
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Siguiente accion</p>
                <InfoPopover
                  title="Siguiente accion"
                  description="Orienta el siguiente paso recomendado en funcion del contexto que tengas activo."
                  items={[
                    'Lo habitual es alternar entre subir nuevos lotes y revisar la bandeja documental.',
                  ]}
                  align="left"
                  widthClass="w-64"
                />
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {selectedCompanyDetails
                  ? `Puedes subir un nuevo lote para ${selectedCompanyDetails.nombre} o revisar su bandeja documental.`
                  : 'Selecciona una empresa o continua revisando el global de la asesoria.'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Charts statsByState={statsByState} />
        <RecentActivity activities={stats?.actividad_reciente || []} loading={statsLoading} />
      </div>
    </div>
  );
}
