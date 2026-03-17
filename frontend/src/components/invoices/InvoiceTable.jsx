import { Link } from 'react-router-dom';
import { formatDate, formatCurrency } from '../../utils/formatters';
import { INVOICE_STATE_LABELS, INVOICE_STATE_COLORS, INVOICE_TYPE_LABELS } from '../../utils/constants';
import ConfidenceBadge from '../common/ConfidenceBadge';

export default function InvoiceTable({ invoices = [] }) {
  if (invoices.length === 0) {
    return (
      <div className="card p-10 text-center">
        <svg className="w-12 h-12 text-slate-200 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
        <p className="text-sm text-slate-400">No se encontraron facturas</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              <th className="text-left px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Factura</th>
              <th className="text-left px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Proveedor / Cliente</th>
              <th className="text-left px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Tipo</th>
              <th className="text-right px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Total</th>
              <th className="text-center px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Confianza</th>
              <th className="text-center px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Estado</th>
              <th className="text-right px-5 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wider">Fecha</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {invoices.map((inv) => (
              <tr key={inv.id} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-5 py-3.5">
                  <Link to={`/invoices/review/${inv.id}`} className="font-semibold text-blue-600 hover:text-blue-800">
                    {inv.numero_factura || `#${inv.id}`}
                  </Link>
                </td>
                <td className="px-5 py-3.5 text-slate-600 truncate max-w-[200px]">
                  {inv.proveedor_nombre || inv.cliente_nombre || '—'}
                </td>
                <td className="px-5 py-3.5">
                  <span className="badge bg-slate-100 text-slate-600">
                    {INVOICE_TYPE_LABELS[inv.tipo] || inv.tipo || '—'}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-right font-semibold text-slate-800">
                  {formatCurrency(inv.total)}
                </td>
                <td className="px-5 py-3.5 text-center">
                  <ConfidenceBadge value={inv.confianza_extraccion} />
                </td>
                <td className="px-5 py-3.5 text-center">
                  <span className={`badge ${INVOICE_STATE_COLORS[inv.estado] || 'bg-slate-100 text-slate-600'}`}>
                    {INVOICE_STATE_LABELS[inv.estado] || inv.estado}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-right text-slate-500 text-xs">
                  {formatDate(inv.fecha_factura || inv.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden divide-y divide-slate-100">
        {invoices.map((inv) => (
          <Link key={inv.id} to={`/invoices/review/${inv.id}`} className="block p-4 hover:bg-slate-50 transition-colors">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-blue-600">{inv.numero_factura || `#${inv.id}`}</span>
              <span className={`badge ${INVOICE_STATE_COLORS[inv.estado] || 'bg-slate-100 text-slate-600'}`}>
                {INVOICE_STATE_LABELS[inv.estado] || inv.estado}
              </span>
            </div>
            <p className="text-sm text-slate-600 truncate">{inv.proveedor_nombre || inv.cliente_nombre || '—'}</p>
            <div className="flex items-center justify-between mt-2">
              <span className="text-sm font-semibold text-slate-800">{formatCurrency(inv.total)}</span>
              <span className="text-xs text-slate-400">{formatDate(inv.fecha_factura || inv.created_at)}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
