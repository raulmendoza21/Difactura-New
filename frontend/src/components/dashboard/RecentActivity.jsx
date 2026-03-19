import LoadingSpinner from '../common/LoadingSpinner';
import { formatDateTime } from '../../utils/formatters';
import InfoPopover from '../common/InfoPopover';

const ACTION_LABELS = {
  SUBIDA: 'Subida',
  VALIDADA: 'Validada',
  RECHAZADA: 'Rechazada',
  ACTUALIZADA: 'Actualizada',
};

const ACTION_COLORS = {
  SUBIDA: 'bg-blue-50 text-blue-700',
  VALIDADA: 'bg-emerald-50 text-emerald-700',
  RECHAZADA: 'bg-red-50 text-red-700',
  ACTUALIZADA: 'bg-amber-50 text-amber-700',
};

function getActionLabel(action) {
  return ACTION_LABELS[action] || action || 'Actividad';
}

export default function RecentActivity({ activities = [], loading = false }) {
  if (loading) {
    return (
      <div className="card p-6">
        <h3 className="text-base font-semibold text-slate-800 mb-4">Actividad reciente</h3>
        <LoadingSpinner text="Cargando actividad..." />
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="card p-6">
        <h3 className="text-base font-semibold text-slate-800 mb-4">Actividad reciente</h3>
        <div className="text-center py-8">
          <svg className="w-10 h-10 text-slate-200 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-slate-400">Sin actividad reciente</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-800">Actividad reciente</h3>
            <InfoPopover
              title="Actividad reciente"
              description="Muestra los ultimos movimientos registrados sobre facturas y acciones humanas."
              items={[
                'Sirve para seguir validaciones, rechazos, subidas y actualizaciones.',
                'Se actualiza segun el contexto activo de la asesoria.',
              ]}
              widthClass="w-72"
              align="left"
            />
          </div>
          <p className="text-xs text-slate-400 mt-1">Ultimos movimientos registrados en la asesoria.</p>
        </div>
        <span className="text-xs font-medium text-slate-400">{activities.length} eventos</span>
      </div>

      <div className="space-y-3">
        {activities.map((activity) => (
          <div
            key={activity.id}
            className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-slate-50/70 px-4 py-3"
          >
            <div className="mt-1 h-2.5 w-2.5 rounded-full bg-blue-500 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm text-slate-700">
                  <span className="font-semibold text-slate-900">
                    {activity.usuario_nombre || 'Sistema'}
                  </span>{' '}
                  marco la factura{' '}
                  <span className="font-semibold text-slate-900">
                    {activity.numero_factura || `#${activity.factura_id || activity.id}`}
                  </span>
                </p>
                <span className={`badge ${ACTION_COLORS[activity.accion] || 'bg-slate-100 text-slate-600'}`}>
                  {getActionLabel(activity.accion)}
                </span>
              </div>

              <p className="mt-1 text-xs text-slate-500">
                {activity.detalle_json?.archivo
                  ? `Archivo: ${activity.detalle_json.archivo}`
                  : 'Sin detalle adicional'}
              </p>
              <p className="mt-1 text-xs text-slate-400">{formatDateTime(activity.created_at)}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
