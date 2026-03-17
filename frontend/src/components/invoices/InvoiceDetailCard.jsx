import { formatCurrency, formatDate } from '../../utils/formatters';
import { INVOICE_STATE_LABELS, INVOICE_STATE_COLORS, INVOICE_TYPE_LABELS } from '../../utils/constants';
import ConfidenceBadge from '../common/ConfidenceBadge';

export default function InvoiceDetailCard({ invoice }) {
  if (!invoice) return null;

  const invoiceType = invoice.tipo?.toUpperCase?.() || invoice.tipo;
  const confidenceValue = invoice.confianza_ia != null ? invoice.confianza_ia * 100 : null;
  const ivaPercent = invoice.iva_porcentaje != null ? `${invoice.iva_porcentaje}%` : '—';

  const fields = [
    { label: 'Numero', value: invoice.numero_factura || '—' },
    { label: 'Tipo', value: INVOICE_TYPE_LABELS[invoiceType] || invoice.tipo || '—' },
    { label: 'Fecha factura', value: formatDate(invoice.fecha) },
    { label: 'Fecha procesado', value: formatDate(invoice.fecha_procesado) },
    { label: 'Proveedor', value: invoice.proveedor_nombre || '—' },
    { label: 'CIF Proveedor', value: invoice.proveedor_cif || '—' },
    { label: 'Cliente', value: invoice.cliente_nombre || '—' },
    { label: 'CIF Cliente', value: invoice.cliente_cif || '—' },
  ];

  const amounts = [
    { label: 'Base imponible', value: formatCurrency(invoice.base_imponible) },
    { label: 'IVA', value: `${ivaPercent} — ${formatCurrency(invoice.iva_importe)}` },
    { label: 'Total', value: formatCurrency(invoice.total), bold: true },
  ];

  return (
    <div className="card divide-y divide-slate-100">
      <div className="p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold text-slate-800">
            {invoice.numero_factura || `Factura #${invoice.id}`}
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">ID: {invoice.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <ConfidenceBadge value={confidenceValue} size="lg" />
          <span className={`badge ${INVOICE_STATE_COLORS[invoice.estado] || 'bg-slate-100 text-slate-600'} px-3 py-1.5 text-sm`}>
            {INVOICE_STATE_LABELS[invoice.estado] || invoice.estado}
          </span>
        </div>
      </div>

      <div className="p-5">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Informacion general</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
          {fields.map((field) => (
            <div key={field.label}>
              <dt className="text-xs text-slate-400">{field.label}</dt>
              <dd className="text-sm font-medium text-slate-700 mt-0.5">{field.value}</dd>
            </div>
          ))}
        </div>
      </div>

      <div className="p-5 bg-slate-50/50">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Importes</h4>
        <div className="space-y-2">
          {amounts.map((amount) => (
            <div key={amount.label} className="flex justify-between items-center">
              <span className={`text-sm ${amount.bold ? 'font-bold text-slate-800' : 'text-slate-500'}`}>{amount.label}</span>
              <span className={`text-sm ${amount.bold ? 'font-bold text-slate-800 text-lg' : 'font-medium text-slate-700'}`}>{amount.value}</span>
            </div>
          ))}
        </div>
      </div>

      {invoice.notas && (
        <div className="p-5">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Notas</h4>
          <p className="text-sm text-slate-600">{invoice.notas}</p>
        </div>
      )}
    </div>
  );
}
