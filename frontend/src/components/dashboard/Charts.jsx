import { memo } from 'react';
import { INVOICE_STATE_LABELS } from '../../utils/constants';
import { getNextMilestone } from '../../utils/billing';
import InfoPopover from '../common/InfoPopover';

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

export default memo(function Charts({ statsByState = {}, processedTotal = 0 }) {
  const states = Object.entries(statsByState).filter(([, count]) => count > 0);
  const total = states.reduce((sum, [, count]) => sum + count, 0);
  const max = Math.max(...states.map(([, count]) => count), 1);

  // Hito siguiente para visualizar el avance de documentos procesados (tarificacion futura por doc).
  // Configurable en frontend/src/utils/billing.js o via VITE_BILLING_MILESTONES.
  const nextMilestone = getNextMilestone(processedTotal);
  const processedPct = Math.min(100, Math.round((processedTotal / nextMilestone) * 100));

  const ProcessedBar = (
    <div className="mb-5 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Documentos procesados
          </p>
          <InfoPopover
            title="Documentos procesados"
            description="Total acumulado de documentos que la asesoria ha procesado en el contexto activo."
            items={[
              'En el futuro la tarificacion se hara por documento procesado.',
              'La barra avanza hacia el siguiente hito de volumen para visualizar el consumo.',
            ]}
            widthClass="w-72"
            align="left"
          />
        </div>
        <span className="text-xs font-medium text-slate-500">
          {processedTotal} / {nextMilestone}
        </span>
      </div>
      <div className="mt-3 w-full bg-white border border-slate-100 rounded-full h-2.5 overflow-hidden">
        <div
          className="h-2.5 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-500"
          style={{ width: `${processedPct}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-slate-400">
        {processedTotal === 0
          ? 'Aun no hay documentos procesados en este contexto.'
          : `Llevas ${processedTotal} documento${processedTotal === 1 ? '' : 's'} procesado${processedTotal === 1 ? '' : 's'}.`}
      </p>
    </div>
  );

  if (states.length === 0) {
    return (
      <div className="card p-6">
        <h3 className="text-base font-semibold text-slate-800 mb-4">Estado de la bandeja</h3>
        {ProcessedBar}
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
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-800">Estado de la bandeja</h3>
            <InfoPopover
              title="Estado de la bandeja"
              description="Resume como se reparte el trabajo documental dentro del contexto activo."
              items={[
                'Los estados del flujo documental ayudan a detectar cuellos de botella en la cola.',
                'Pendientes y errores son los bloques que conviene atender primero.',
              ]}
              widthClass="w-72"
              align="left"
            />
          </div>
          <p className="text-xs text-slate-400 mt-1">Distribucion actual de documentos por estado.</p>
        </div>
        <span className="text-sm text-slate-400">{total} total</span>
      </div>

      {ProcessedBar}

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
})
