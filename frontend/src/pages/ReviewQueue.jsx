import { useState } from 'react';
import { Link } from 'react-router-dom';
import InvoiceTable from '../components/invoices/InvoiceTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import StatusPanel from '../components/common/StatusPanel';
import { useInvoices } from '../hooks/useInvoices';
import { INVOICE_STATES, INVOICE_STATE_LABELS } from '../utils/constants';

const REVIEW_QUEUE_STATES = [
  INVOICE_STATES.PENDIENTE_REVISION,
  INVOICE_STATES.EN_PROCESO,
  INVOICE_STATES.SUBIDA,
  INVOICE_STATES.ERROR_PROCESAMIENTO,
];

export default function ReviewQueue() {
  const [estado, setEstado] = useState(INVOICE_STATES.PENDIENTE_REVISION);
  const { invoices, pagination, loading, updateParams } = useInvoices({
    page: 1,
    limit: 20,
    estado: INVOICE_STATES.PENDIENTE_REVISION,
  });

  const handleStatusChange = (nextStatus) => {
    setEstado(nextStatus);
    updateParams({ estado: nextStatus, page: 1 });
  };

  const totalPages = Math.ceil(pagination.total / pagination.limit) || 1;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
            Bandeja operativa
          </p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Pendientes de validacion</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Aqui aparecen los documentos que ya han entrado en el circuito y necesitan seguimiento:
            procesando, pendientes de revisar o con error.
          </p>
        </div>

        <Link to="/invoices/upload" className="btn-secondary">
          Subir mas documentos
        </Link>
      </div>

      <StatusPanel
        tone="info"
        eyebrow="Cola de revision"
        title="Seguimiento de documentos pendientes"
        description="Aqui puedes revisar el estado de entrada y abrir los documentos que ya estan listos para validar."
        items={[
          'Pendiente de revision muestra lo que ya puedes abrir y revisar.',
          'En proceso y subida te ayudan a seguir la entrada del lote.',
          'Error de procesamiento identifica documentos que requieren reproceso.',
        ]}
        compact
      />

      <div className="flex flex-wrap gap-2">
        {REVIEW_QUEUE_STATES.map((status) => {
          const active = estado === status;
          return (
            <button
              key={status}
              type="button"
              onClick={() => handleStatusChange(status)}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                active
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:text-slate-900'
              }`}
            >
              {INVOICE_STATE_LABELS[status] || status}
            </button>
          );
        })}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <p className="text-sm text-slate-500">
          {pagination.total} factura{pagination.total !== 1 ? 's' : ''} en estado{' '}
          <span className="font-semibold text-slate-700">
            {INVOICE_STATE_LABELS[estado] || estado}
          </span>
        </p>
      </div>

      {loading ? (
        <LoadingSpinner text="Cargando cola de revision..." />
      ) : (
        <>
          <InvoiceTable invoices={invoices} />

          {invoices.length === 0 && (
            <StatusPanel
              tone="success"
              eyebrow="Sin resultados"
              title="No hay documentos en este estado"
              description="Cuando entren nuevos documentos o cambie su estado, apareceran aqui automaticamente."
              compact
            />
          )}
        </>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => updateParams({ page: pagination.page - 1 })}
            disabled={pagination.page <= 1}
            className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-30"
          >
            Anterior
          </button>
          <span className="text-sm text-slate-500">
            Pagina {pagination.page} de {totalPages}
          </span>
          <button
            onClick={() => updateParams({ page: pagination.page + 1 })}
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
