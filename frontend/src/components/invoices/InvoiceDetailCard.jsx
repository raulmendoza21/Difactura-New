import { formatCurrency, formatDate } from '../../utils/formatters';
import { INVOICE_STATE_COLORS, INVOICE_STATE_LABELS } from '../../utils/constants';
import ConfidenceBadge from '../common/ConfidenceBadge';
import { isFieldSuspicious } from './FieldConfidenceHint';

const OPERATION_SIDE_LABELS = {
  compra: 'Compra',
  venta: 'Venta',
  unknown: 'Desconocido',
};

// Map display fields → field_confidence keys
const FIELD_CONFIDENCE_MAP = {
  'Numero': 'numero_factura',
  'Fecha factura': 'fecha',
  'Emisor': 'proveedor',
  'NIF emisor': 'cif_proveedor',
  'Receptor': 'cliente',
  'NIF receptor': 'cif_cliente',
  'Base imponible': 'base_imponible',
  'Total': 'total',
};

function FieldIndicator({ confidence, isMissing, isInferred }) {
  if (isMissing) {
    return (
      <span
        title="Dato no detectado en el documento"
        className="inline-block ml-1.5 h-2.5 w-2.5 rounded-full bg-red-400 ring-2 ring-red-100"
      />
    );
  }
  if (isInferred || isFieldSuspicious(confidence)) {
    return (
      <span
        title="Dato con baja confianza — revisar manualmente"
        className="inline-block ml-1.5 h-2.5 w-2.5 rounded-full bg-amber-400 ring-2 ring-amber-100"
      />
    );
  }
  return null;
}

export default function InvoiceDetailCard({ invoice }) {
  if (!invoice) return null;

  const json = invoice.documento_json || {};
  const nd = json.normalized_document || {};
  const fieldConfidence = json.field_confidence || {};
  const missingFields = json.missing_fields || [];
  const inferredFields = json.inferred_fields || [];

  const rawConfidence = Number(invoice.confianza_ia ?? json.confianza);
  const confidenceValue = Number.isFinite(rawConfidence) && rawConfidence > 0 ? rawConfidence * 100 : null;

  const operationSide = json.operation_side || 'unknown';
  const taxLabel = (json.tax_regime || nd.classification?.tax_regime || 'IVA').toUpperCase();
  const taxBreakdown = nd.tax_breakdown || [];
  const withholding = nd.withholdings?.[0] || null;
  const paymentInfo = nd.payment_info || {};
  const observaciones = json.observaciones || nd.observaciones || null;

  const fields = [
    { label: 'Numero', value: json.numero_factura || '-' },
    { label: 'Tipo operacion', value: OPERATION_SIDE_LABELS[operationSide] || operationSide },
    { label: 'Tipo documento', value: json.tipo_factura || json.document_type || '-' },
    { label: 'Fecha factura', value: formatDate(json.fecha) },
    { label: 'Fecha procesado', value: formatDate(invoice.fecha_procesado) },
    { label: 'Emisor', value: json.proveedor || nd.issuer?.name || '-' },
    { label: 'NIF emisor', value: json.cif_proveedor || nd.issuer?.tax_id || '-' },
    { label: 'Receptor', value: json.cliente || nd.recipient?.name || '-' },
    { label: 'NIF receptor', value: json.cif_cliente || nd.recipient?.tax_id || '-' },
    { label: 'Empresa asociada', value: invoice.empresa_asociada?.nombre || '-' },
  ];

  // Importes
  const hasBreakdown = taxBreakdown.length > 1;
  const amountsBase = [
    { label: 'Base imponible', value: formatCurrency(json.base_imponible) },
  ];
  if (hasBreakdown) {
    taxBreakdown.forEach((tb) => {
      const regime = (tb.tax_regime || taxLabel).toUpperCase();
      amountsBase.push({
        label: `${regime} ${tb.rate != null ? tb.rate + '%' : ''}`.trim(),
        value: `Base ${formatCurrency(tb.taxable_base)} · Cuota ${formatCurrency(tb.tax_amount)}`,
        isTax: true,
      });
    });
  } else {
    const taxPercent = json.iva_porcentaje != null ? `${json.iva_porcentaje}%` : '-';
    amountsBase.push({ label: taxLabel, value: `${taxPercent} · ${formatCurrency(json.iva)}` });
  }
  if (withholding) {
    amountsBase.push({
      label: `Retención ${withholding.withholding_type || ''}`.trim(),
      value: `${Number(withholding.rate || 0).toFixed(2)}% · -${formatCurrency(withholding.amount || 0)}`,
    });
  }
  amountsBase.push({ label: 'Total', value: formatCurrency(json.total), bold: true });

  return (
    <div className="card divide-y divide-slate-100">
      <div className="p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold text-slate-800">
            {json.numero_factura || `Factura #${invoice.id}`}
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

      {(missingFields.length > 0 || inferredFields.length > 0) && (
        <div className="px-5 py-2.5 bg-amber-50/50 flex flex-wrap items-center gap-4 text-xs text-slate-500">
          {missingFields.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-red-400 ring-2 ring-red-100" />
              Dato no detectado ({missingFields.length})
            </span>
          )}
          {inferredFields.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400 ring-2 ring-amber-100" />
              Baja confianza — revisar ({inferredFields.length})
            </span>
          )}
        </div>
      )}

      <div className="p-5">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Informacion general</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
          {fields.map((field) => {
            const confKey = FIELD_CONFIDENCE_MAP[field.label];
            const conf = confKey ? fieldConfidence[confKey] : null;
            const isMissing = confKey ? missingFields.includes(confKey) : false;
            const isInferred = confKey ? inferredFields.includes(confKey) : false;
            return (
              <div key={field.label}>
                <dt className="text-xs text-slate-400 flex items-center">
                  {field.label}
                  {confKey && <FieldIndicator confidence={conf} isMissing={isMissing} isInferred={isInferred} />}
                </dt>
                <dd className={`text-sm font-medium mt-0.5 ${isMissing ? 'text-slate-400 italic' : 'text-slate-700'}`}>{field.value}</dd>
              </div>
            );
          })}
        </div>
      </div>

      <div className="p-5 bg-slate-50/50">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Importes</h4>
        <div className="space-y-2">
          {amountsBase.map((amount) => (
            <div key={amount.label} className="flex justify-between items-center gap-4">
              <span className={`text-sm ${amount.bold ? 'font-bold text-slate-800' : 'text-slate-500'}`}>
                {amount.label}
              </span>
              <span className={`text-sm ${amount.bold ? 'font-bold text-slate-800 text-lg' : 'font-medium text-slate-700'}`}>
                {amount.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {(paymentInfo?.forma_pago || paymentInfo?.cuenta_bancaria || paymentInfo?.fecha_vencimiento || paymentInfo?.condiciones_pago) && (
        <div className="p-5">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Pago</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
            {paymentInfo.forma_pago && (
              <div>
                <dt className="text-xs text-slate-400">Forma de pago</dt>
                <dd className="text-sm font-medium text-slate-700 mt-0.5 capitalize">{paymentInfo.forma_pago}</dd>
              </div>
            )}
            {paymentInfo.condiciones_pago && (
              <div>
                <dt className="text-xs text-slate-400">Condiciones</dt>
                <dd className="text-sm font-medium text-slate-700 mt-0.5">{paymentInfo.condiciones_pago}</dd>
              </div>
            )}
            {paymentInfo.fecha_vencimiento && (
              <div>
                <dt className="text-xs text-slate-400">Vencimiento</dt>
                <dd className="text-sm font-medium text-slate-700 mt-0.5">{formatDate(paymentInfo.fecha_vencimiento)}</dd>
              </div>
            )}
            {paymentInfo.cuenta_bancaria && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-slate-400">IBAN</dt>
                <dd className="text-sm font-mono font-medium text-slate-700 mt-0.5 tracking-wide">{paymentInfo.cuenta_bancaria}</dd>
              </div>
            )}
          </div>
        </div>
      )}

      {observaciones && (
        <div className="p-5">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Observaciones</h4>
          <p className="text-sm text-slate-600">{observaciones}</p>
        </div>
      )}
    </div>
  );
}
