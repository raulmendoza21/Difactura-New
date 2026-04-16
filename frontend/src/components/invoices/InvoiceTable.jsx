import { memo } from 'react';
import { Link } from 'react-router-dom';
import { formatDate, formatDateTime, formatCurrency } from '../../utils/formatters';
import {
  INVOICE_STATE_LABELS,
  INVOICE_STATE_COLORS,
  JOB_STATE_LABELS,
  JOB_STATE_COLORS,
  INVOICE_STATES,
  DOCUMENT_CHANNEL_LABELS,
} from '../../utils/constants';
import ConfidenceBadge from '../common/ConfidenceBadge';

const OPERATION_SIDE_LABELS = {
  compra: 'Compra',
  venta: 'Venta',
  unknown: 'Desconocido',
};

function getInvoiceDate(invoice) {
  return invoice.documento_json?.fecha || invoice.created_at;
}

function getInvoiceConfidence(invoice) {
  return invoice.confianza_ia ?? invoice.documento_json?.confianza;
}

function canReprocess(invoice) {
  return ![INVOICE_STATES.SUBIDA, INVOICE_STATES.EN_PROCESO, INVOICE_STATES.VALIDADA].includes(invoice.estado);
}

function getChannelLabel(channel) {
  if (!channel) return 'Sin canal';
  return DOCUMENT_CHANNEL_LABELS[channel] || channel;
}

function getCounterpartyName(invoice) {
  const json = invoice.documento_json || {};
  return (
    json.proveedor ||
    json.normalized_document?.issuer?.name ||
    '-'
  );
}

function getAssociatedCompanyName(invoice) {
  return invoice.empresa_asociada?.nombre || '-';
}

export default memo(function InvoiceTable({
  invoices = [],
  scrollable = false,
  maxHeightClass = 'h-[32rem]',
  onReprocess,
  actionInvoiceId = null,
}) {
  if (invoices.length === 0) {
    return (
      <div className="card p-10 text-center">
        <svg className="w-12 h-12 text-slate-200 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-sm text-slate-400">No se encontraron facturas</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className={`hidden md:block overflow-x-auto ${scrollable ? `${maxHeightClass} overflow-y-scroll` : ''}`}>
        <table className="w-full text-sm">
          <thead>
            <tr className={`bg-slate-50/80 border-b border-slate-100 ${scrollable ? 'sticky top-0 z-10 backdrop-blur-sm' : ''}`}>
              <th className="text-left px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Factura</th>
              <th className="text-left px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Contraparte / Empresa</th>
              <th className="text-left px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Cola</th>
              <th className="text-left px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Tipo</th>
              <th className="text-right px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Total</th>
              <th className="text-center px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Confianza</th>
              <th className="text-center px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Estado</th>
              <th className="text-right px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Fecha</th>
              <th className="text-right px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {invoices.map((invoice) => (
              <tr key={invoice.id} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-5 py-3.5">
                  <div className="space-y-1">
                    <Link to={`/invoices/review/${invoice.id}`} className="font-semibold text-blue-600 hover:text-blue-800">
                      {invoice.documento_json?.numero_factura || `#${invoice.id}`}
                    </Link>
                    <p className="text-xs text-slate-400">
                      {invoice.documento?.nombre_archivo || `Documento #${invoice.id}`}
                    </p>
                    {invoice.documento?.batch_id && (
                      <p className="text-xs text-slate-400">
                        Lote {invoice.documento.batch_id} · {getChannelLabel(invoice.documento.canal_entrada)}
                      </p>
                    )}
                  </div>
                </td>
                <td className="px-5 py-3.5 max-w-[240px]">
                  <div className="space-y-1">
                    <p className="truncate text-slate-700">{getCounterpartyName(invoice)}</p>
                    <p className="text-xs text-slate-400">
                      {getAssociatedCompanyName(invoice) !== '-'
                        ? `Empresa asociada: ${getAssociatedCompanyName(invoice)}`
                        : 'Sin empresa asociada'}
                    </p>
                  </div>
                </td>
                <td className="px-5 py-3.5">
                  {invoice.job ? (
                    <div className="space-y-1">
                      <span className={`badge ${JOB_STATE_COLORS[invoice.job.estado] || 'bg-slate-100 text-slate-600'}`}>
                        {JOB_STATE_LABELS[invoice.job.estado] || invoice.job.estado}
                      </span>
                      <div className="text-xs text-slate-400">
                        {invoice.job.finished_at
                          ? `Finalizado ${formatDateTime(invoice.job.finished_at)}`
                          : invoice.job.started_at
                            ? `Iniciado ${formatDateTime(invoice.job.started_at)}`
                            : 'Esperando worker'}
                      </div>
                      {invoice.job.retry_count > 0 && (
                        <div className="text-xs text-amber-600">Reintentos: {invoice.job.retry_count}</div>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">Sin job</span>
                  )}
                </td>
                <td className="px-5 py-3.5">
                  <span className="badge bg-slate-100 text-slate-600">
                    {OPERATION_SIDE_LABELS[invoice.documento_json?.operation_side] || '-'}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-right font-semibold text-slate-800">
                  {formatCurrency(invoice.documento_json?.total)}
                </td>
                <td className="px-5 py-3.5 text-center">
                  <ConfidenceBadge value={getInvoiceConfidence(invoice)} />
                </td>
                <td className="px-5 py-3.5 text-center">
                  <span className={`badge ${INVOICE_STATE_COLORS[invoice.estado] || 'bg-slate-100 text-slate-600'}`}>
                    {INVOICE_STATE_LABELS[invoice.estado] || invoice.estado}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-right text-slate-500 text-xs">
                  {formatDate(getInvoiceDate(invoice))}
                </td>
                <td className="px-5 py-3.5">
                  <div className="flex items-center justify-end gap-2">
                    <Link to={`/invoices/review/${invoice.id}`} className="btn-secondary px-3 py-1.5 text-xs">
                      Abrir
                    </Link>
                    {onReprocess && canReprocess(invoice) && (
                      <button
                        type="button"
                        onClick={() => onReprocess(invoice)}
                        disabled={actionInvoiceId === invoice.id}
                        className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-50"
                      >
                        {actionInvoiceId === invoice.id ? 'Relanzando...' : 'Reprocesar'}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={`md:hidden divide-y divide-slate-100 ${scrollable ? `${maxHeightClass} overflow-y-scroll` : ''}`}>
        {invoices.map((invoice) => (
          <div key={invoice.id} className="p-4 hover:bg-slate-50 transition-colors space-y-3">
            <Link to={`/invoices/review/${invoice.id}`} className="block">
              <div className="flex items-center justify-between mb-2 gap-3">
                <span className="font-semibold text-blue-600">{invoice.documento_json?.numero_factura || `#${invoice.id}`}</span>
                <span className={`badge ${INVOICE_STATE_COLORS[invoice.estado] || 'bg-slate-100 text-slate-600'}`}>
                  {INVOICE_STATE_LABELS[invoice.estado] || invoice.estado}
                </span>
              </div>
              <p className="text-sm text-slate-600 truncate">{getCounterpartyName(invoice)}</p>
              <p className="mt-1 text-xs text-slate-400 truncate">
                {getAssociatedCompanyName(invoice) !== '-'
                  ? `Empresa asociada: ${getAssociatedCompanyName(invoice)}`
                  : 'Sin empresa asociada'}
              </p>
              {invoice.documento?.batch_id && (
                <p className="mt-1 text-xs text-slate-400">
                  {invoice.documento.batch_id} · {getChannelLabel(invoice.documento.canal_entrada)}
                </p>
              )}
              <div className="flex items-center justify-between mt-2">
                <span className="text-sm font-semibold text-slate-800">{formatCurrency(invoice.documento_json?.total)}</span>
                <span className="text-xs text-slate-400">{formatDate(getInvoiceDate(invoice))}</span>
              </div>
              {invoice.job && (
                <div className="mt-3 flex items-center justify-between gap-2">
                  <span className={`badge ${JOB_STATE_COLORS[invoice.job.estado] || 'bg-slate-100 text-slate-600'}`}>
                    {JOB_STATE_LABELS[invoice.job.estado] || invoice.job.estado}
                  </span>
                  <span className="text-xs text-slate-400">
                    {invoice.job.finished_at
                      ? formatDateTime(invoice.job.finished_at)
                      : invoice.job.started_at
                        ? formatDateTime(invoice.job.started_at)
                        : 'En cola'}
                  </span>
                </div>
              )}
            </Link>
            <div className="flex gap-2">
              <Link to={`/invoices/review/${invoice.id}`} className="btn-secondary flex-1 text-xs text-center">
                Abrir
              </Link>
              {onReprocess && canReprocess(invoice) && (
                <button
                  type="button"
                  onClick={() => onReprocess(invoice)}
                  disabled={actionInvoiceId === invoice.id}
                  className="btn-secondary flex-1 text-xs disabled:opacity-50"
                >
                  {actionInvoiceId === invoice.id ? 'Relanzando...' : 'Reprocesar'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
})
