import { formatCurrency, formatDate } from '../../utils/formatters';
import { INVOICE_STATE_COLORS, INVOICE_STATE_LABELS, INVOICE_TYPE_LABELS } from '../../utils/constants';
import { getTaxIdLabel, getTaxLabel } from '../../utils/invoicePresentation';
import ConfidenceBadge from '../common/ConfidenceBadge';
import FieldConfidenceHint from './FieldConfidenceHint';

export default function InvoiceDetailCard({ invoice }) {
  if (!invoice) return null;

  const invoiceType = invoice.tipo?.toUpperCase?.() || invoice.tipo;
  const rawConfidence = Number(invoice.confianza_ia);
  const confidenceValue = Number.isFinite(rawConfidence) ? rawConfidence * 100 : null;
  const taxPercent = invoice.iva_porcentaje != null ? `${invoice.iva_porcentaje}%` : '-';
  const taxLabel = getTaxLabel(invoice);
  const taxIdLabel = getTaxIdLabel();
  const fieldConfidence = invoice.extraction?.field_confidence || {};
  const withholding = invoice.extraction?.normalized_document?.withholdings?.[0] || null;
  const associatedCompany = invoice.empresa_asociada || null;
  const detectedIssuer = invoice.extraction?.normalized_document?.issuer || null;
  const detectedRecipient = invoice.extraction?.normalized_document?.recipient || null;
  const counterpartyConfidence =
    invoice.tipo === 'venta' ? fieldConfidence.cliente : fieldConfidence.proveedor;
  const counterpartyTaxConfidence =
    invoice.tipo === 'venta' ? fieldConfidence.cif_cliente : fieldConfidence.cif_proveedor;

  const fields = [
    { label: 'Numero', value: invoice.numero_factura || '-', confidence: fieldConfidence.numero_factura },
    { label: 'Tipo', value: INVOICE_TYPE_LABELS[invoiceType] || invoice.tipo || '-' },
    { label: 'Fecha factura', value: formatDate(invoice.fecha), confidence: fieldConfidence.fecha },
    { label: 'Fecha procesado', value: formatDate(invoice.fecha_procesado) },
    { label: 'Contraparte', value: invoice.proveedor_nombre || '-', confidence: counterpartyConfidence },
    { label: `${taxIdLabel} contraparte`, value: invoice.proveedor_cif || '-', confidence: counterpartyTaxConfidence },
    { label: 'Empresa asociada', value: associatedCompany?.nombre || invoice.cliente_nombre || '-' },
    { label: `${taxIdLabel} empresa`, value: associatedCompany?.cif || invoice.cliente_cif || '-' },
  ];

  const amounts = [
    { label: 'Base imponible', value: formatCurrency(invoice.base_imponible), confidence: fieldConfidence.base_imponible },
    { label: taxLabel, value: `${taxPercent} · ${formatCurrency(invoice.iva_importe)}`, confidence: fieldConfidence.iva },
    { label: 'Total', value: formatCurrency(invoice.total), bold: true, confidence: fieldConfidence.total },
  ];

  if (withholding) {
    amounts.splice(2, 0, {
      label: `Retención ${withholding.withholding_type || ''}`.trim(),
      value: `${Number(withholding.rate || 0).toFixed(2)}% · -${formatCurrency(withholding.amount || 0)}`,
      confidence: null,
    });
  }

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
              <dt className="flex items-center gap-2 text-xs text-slate-400">
                <span>{field.label}</span>
                <FieldConfidenceHint value={field.confidence} label={field.label} compact />
              </dt>
              <dd className="text-sm font-medium text-slate-700 mt-0.5">{field.value}</dd>
            </div>
          ))}
        </div>
      </div>

      {(detectedIssuer?.name || detectedRecipient?.name) && (
        <div className="p-5 bg-slate-50/30">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Partes detectadas en el documento</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
            <div>
              <dt className="flex items-center gap-2 text-xs text-slate-400">
                <span>Emisor detectado</span>
                <FieldConfidenceHint value={fieldConfidence.proveedor} label="Emisor detectado" compact />
              </dt>
              <dd className="text-sm font-medium text-slate-700 mt-0.5">{detectedIssuer?.name || '-'}</dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 text-xs text-slate-400">
                <span>{taxIdLabel} emisor</span>
                <FieldConfidenceHint value={fieldConfidence.cif_proveedor} label={`${taxIdLabel} emisor`} compact />
              </dt>
              <dd className="text-sm font-medium text-slate-700 mt-0.5">{detectedIssuer?.tax_id || '-'}</dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 text-xs text-slate-400">
                <span>Receptor detectado</span>
                <FieldConfidenceHint value={fieldConfidence.cliente} label="Receptor detectado" compact />
              </dt>
              <dd className="text-sm font-medium text-slate-700 mt-0.5">{detectedRecipient?.name || '-'}</dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 text-xs text-slate-400">
                <span>{taxIdLabel} receptor</span>
                <FieldConfidenceHint value={fieldConfidence.cif_cliente} label={`${taxIdLabel} receptor`} compact />
              </dt>
              <dd className="text-sm font-medium text-slate-700 mt-0.5">{detectedRecipient?.tax_id || '-'}</dd>
            </div>
          </div>
        </div>
      )}

      <div className="p-5 bg-slate-50/50">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Importes</h4>
        <div className="space-y-2">
          {amounts.map((amount) => (
            <div key={amount.label} className="flex justify-between items-center gap-4">
              <span className={`flex items-center gap-2 text-sm ${amount.bold ? 'font-bold text-slate-800' : 'text-slate-500'}`}>
                <span>{amount.label}</span>
                <FieldConfidenceHint value={amount.confidence} label={amount.label} compact />
              </span>
              <span className={`text-sm ${amount.bold ? 'font-bold text-slate-800 text-lg' : 'font-medium text-slate-700'}`}>
                {amount.value}
              </span>
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
