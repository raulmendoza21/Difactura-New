import { useState, useEffect } from 'react';
import StatsCard from '../components/dashboard/StatsCard';
import RecentActivity from '../components/dashboard/RecentActivity';
import Charts from '../components/dashboard/Charts';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { getDashboardStats } from '../services/invoiceService';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardStats()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner text="Cargando dashboard..." />;

  const stats = data?.stats || {};
  const recent = data?.recent || [];
  const byState = data?.byState || {};

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Resumen general del sistema</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatsCard
          title="Total facturas"
          value={stats.total || 0}
          icon="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          color="blue"
        />
        <StatsCard
          title="Pendientes revisión"
          value={stats.pendientes || 0}
          icon="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          color="amber"
        />
        <StatsCard
          title="Validadas"
          value={stats.validadas || 0}
          icon="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          color="emerald"
        />
        <StatsCard
          title="Con errores"
          value={stats.errores || 0}
          icon="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
          color="red"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Charts statsByState={byState} />
        <RecentActivity activities={recent} />
      </div>
    </div>
  );
}
