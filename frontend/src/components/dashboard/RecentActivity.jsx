import { formatDate } from '../../utils/formatters';
import { INVOICE_STATE_LABELS, INVOICE_STATE_COLORS } from '../../utils/constants';

export default function RecentActivity({ activities = [] }) {
  if (activities.length === 0) {
    return (
      <div className="card p-6">
        <h3 className="text-base font-semibold text-slate-800 mb-4">Actividad reciente</h3>
        <div className="text-center py-8">
          <svg className="w-10 h-10 text-slate-200 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <p className="text-sm text-slate-400">Sin actividad reciente</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <h3 className="text-base font-semibold text-slate-800 mb-4">Actividad reciente</h3>
      <div className="space-y-3">
        {activities.map((a, i) => (
          <div key={i} className="flex items-center gap-3 py-2 border-b border-slate-50 last:border-0">
            <div className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-slate-700 truncate">
                Factura <span className="font-medium">{a.numero_factura || `#${a.id}`}</span>
              </p>
              <p className="text-xs text-slate-400">{formatDate(a.created_at)}</p>
            </div>
            <span className={`badge ${INVOICE_STATE_COLORS[a.estado] || 'bg-slate-100 text-slate-600'}`}>
              {INVOICE_STATE_LABELS[a.estado] || a.estado}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
