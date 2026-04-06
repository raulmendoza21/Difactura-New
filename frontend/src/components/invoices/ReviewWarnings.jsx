import StatusPanel from '../common/StatusPanel';
import { getTaxIdLabel, getTaxLabel } from '../../utils/invoicePresentation';
import { getNormalizedWarningGroups, hasWarningGroup } from '../../utils/extractionWarnings';

function isValidTaxId(value) {
  if (!value) return false;
  return /^[A-Z0-9][A-Z0-9-]{5,15}$/i.test(String(value).trim());
}

function toNumber(value) {
  if (value == null || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function buildWarnings(invoice) {
  if (!invoice) return [];

  const warnings = [];
  const taxLabel = getTaxLabel(invoice);
  const taxIdLabel = getTaxIdLabel();
  const extractionWarnings = invoice.extraction?.warnings || [];
  const decisionFlags = invoice.extraction?.decision_flags || [];
  const warningGroups = getNormalizedWarningGroups(extractionWarnings);
  const base = toNumber(invoice.base_imponible);
  const tax = toNumber(invoice.iva_importe);
  const total = toNumber(invoice.total);
  const jobError = invoice.job?.error_message;
  const providerTaxId = String(invoice.proveedor_cif || '').trim();
  const companyTaxId = String(invoice.cliente_cif || '').trim();
  const lineSum = Array.isArray(invoice.lineas)
    ? invoice.lineas.reduce((sum, line) => sum + (toNumber(line.subtotal) || 0), 0)
    : 0;
  const totalsAreCoherent =
    base != null && tax != null && total != null && Math.abs(base + tax - total) <= 0.02;
  const linesMatchBase =
    Array.isArray(invoice.lineas) && invoice.lineas.length > 0 && base != null && Math.abs(lineSum - base) <= 0.02;
  const documentType = invoice.extraction?.normalized_document?.classification?.document_type || '';
  const isTicketLike = documentType === 'ticket' || documentType === 'factura_simplificada';
  const hasAutomaticCorrections =
    warningGroups.includes('amount_adjustment')
    || warningGroups.includes('line_item_adjustment')
    || warningGroups.includes('party_adjustment')
    || warningGroups.includes('document_role_adjustment');
  const hasTechnicalDiscrepancies = warningGroups.includes('source_discrepancy');

  decisionFlags.forEach((flag) => {
    if (!flag?.message) return;
    warnings.push({
      tone: flag.severity === 'error' ? 'error' : flag.requires_review ? 'warning' : 'info',
      text: flag.message,
    });
  });

  if (jobError) {
    warnings.push({
      tone: 'error',
      text: `El proceso automatico registro un error: ${jobError}`,
    });
  }

  if (hasWarningGroup(extractionWarnings, 'doc_ai_fallback')) {
    warnings.push({
      tone: 'warning',
      text: 'La lectura automatica utilizo una via complementaria selectiva para cerrar la interpretacion del documento. Conviene revisar los campos clave antes de validar.',
    });
  }

  if (hasWarningGroup(extractionWarnings, 'doc_ai_fallback_error')) {
    warnings.push({
      tone: 'warning',
      text: 'La via complementaria selectiva no estuvo disponible durante parte del proceso. Se ha mantenido la mejor lectura principal disponible.',
    });
  }

  if (!invoice.numero_factura) {
    warnings.push({
      tone: 'warning',
      text: 'Falta el numero de factura.',
    });
  }

  if (!invoice.fecha) {
    warnings.push({
      tone: 'warning',
      text: 'Falta la fecha de la factura.',
    });
  }

  if (!invoice.proveedor_nombre) {
    warnings.push({
      tone: 'warning',
      text: 'Falta identificar la contraparte principal del documento.',
    });
  }

  if (!providerTaxId) {
    warnings.push({
      tone: 'info',
      text: `No se ha podido confirmar el ${taxIdLabel} de la contraparte.`,
    });
  } else if (!isValidTaxId(providerTaxId)) {
    warnings.push({
      tone: 'warning',
      text: `El ${taxIdLabel} de la contraparte no se ha podido validar con suficiente fiabilidad: ${invoice.proveedor_cif}.`,
    });
  }

  if (companyTaxId && !isValidTaxId(companyTaxId)) {
    warnings.push({
      tone: 'info',
      text: `El ${taxIdLabel} de la empresa asociada parece incompleto o poco fiable: ${invoice.cliente_cif}.`,
    });
  }

  if (base != null && tax != null && total != null) {
    const delta = Math.abs(base + tax - total);
    if (delta > 0.02) {
      warnings.push({
        tone: 'warning',
        text: `Los importes no cuadran todavia: base (${base.toFixed(2)}) + ${taxLabel} (${tax.toFixed(2)}) no coincide con el total (${total.toFixed(2)}).`,
      });
    }
  }

  if (!isTicketLike && Array.isArray(invoice.lineas) && invoice.lineas.length > 0 && base != null) {
    if (Math.abs(lineSum - base) > 0.02) {
      warnings.push({
        tone: 'warning',
        text: `La suma de lineas (${lineSum.toFixed(2)}) no coincide con la base imponible (${base.toFixed(2)}).`,
      });
    }
  }

  if (!invoice.lineas || invoice.lineas.length === 0) {
    warnings.push({
      tone: 'info',
      text: 'No se han detectado lineas de detalle. Puedes completarlas manualmente si te hacen falta.',
    });
  }

  if (totalsAreCoherent && hasTechnicalDiscrepancies) {
    warnings.push({
      tone: 'info',
      text: 'El documento presento diferencias entre lecturas alternativas, pero el resultado final ya se ha reconciliado con la opcion mas coherente.',
    });
  }

  if (linesMatchBase && hasAutomaticCorrections) {
    warnings.push({
      tone: 'info',
      text: 'Se han aplicado ajustes automaticos sobre el detalle del documento y el resultado final ya es coherente con los importes detectados.',
    });
  }

  if (isTicketLike) {
    warnings.push({
      tone: 'info',
      text: 'El documento se ha tratado como ticket o factura simplificada. En este tipo de justificantes es normal que algunos datos fiscales o del cliente no aparezcan completos.',
    });
  }

  return dedupeWarnings(warnings);
}

function dedupeWarnings(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = `${item.tone}:${item.text}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function ReviewWarnings({ invoice }) {
  const warnings = buildWarnings(invoice);

  if (warnings.length === 0) {
    return (
      <StatusPanel
        tone="success"
        eyebrow="Revision automatica"
        title="Sin incidencias detectadas"
        description="No se han detectado incoherencias claras. Aun asi, puedes revisar cualquier campo antes de validar."
        compact
      />
    );
  }

  const hasError = warnings.some((warning) => warning.tone === 'error');
  const hasWarning = warnings.some((warning) => warning.tone === 'warning');
  const tone = hasError ? 'error' : hasWarning ? 'warning' : 'info';

  return (
    <StatusPanel
      tone={tone}
      eyebrow="Comprobaciones sugeridas"
      title="Revisa estos campos antes de validar"
      description="Estas comprobaciones se generan automaticamente para ayudarte a detectar posibles errores."
      items={warnings.map((warning) => warning.text)}
      footer="Si hace falta, puedes corregirlos desde Editar datos."
      compact
    />
  );
}
