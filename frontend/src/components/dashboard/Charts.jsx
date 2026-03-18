import { INVOICE_STATE_LABELS } from '../../utils/constants';

const BAR_COLORS = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-purple-500',
  'bg-red-500',
  'bg-cyan-500',
  'bg-pink-500',
  'bg-indigo-500',
];

export default function Charts({ statsByState = {} }) {
  const states = Object.entries(statsByState).filter(([, count]) => count > 0);
  const total = states.reduce((sum, [, count]) => sum + count, 0);
  const max = Math.max(...states.map(([, count]) => count), 1);

  if (states.length === 0) {
    return (
      <div className="card p-6">
        <h3 className="text-base font-semibold text-slate-800 mb-4">Estado de la bandeja</h3>
        <div className="text-center py-8">
          <svg className="w-10 h-10 text-slate-200 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="text-sm text-slate-400">Sin datos disponibles</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-800">Estado de la bandeja</h3>
          <p className="text-xs text-slate-400 mt-1">Distribucion actual de documentos por estado.</p>
        </div>
        <span className="text-sm text-slate-400">{total} total</span>
      </div>

      <div className="space-y-3">
        {states.map(([state, count], index) => {
          const pct = Math.round((count / max) * 100);
          return (
            <div key={state}>
              <div className="flex items-center justify-between text-sm mb-1.5">
                <span className="text-slate-600 font-medium">{INVOICE_STATE_LABELS[state] || state}</span>
                <span className="text-slate-800 font-semibold">{count}</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${BAR_COLORS[index % BAR_COLORS.length]} transition-all duration-500`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
