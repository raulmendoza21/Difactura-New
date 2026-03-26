import StatusPanel from '../common/StatusPanel';
import { getTaxIdLabel, getTaxLabel } from '../../utils/invoicePresentation';

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
  const warningSet = new Set(extractionWarnings);
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
  const hasAutomaticCorrections =
    warningSet.has('importes_corregidos_con_resumen_fallback')
    || warningSet.has('lineas_corregidas_con_fallback')
    || warningSet.has('lineas_enriquecidas_con_fallback')
    || warningSet.has('lineas_completadas_con_fallback')
    || extractionWarnings.some((code) => /^linea_\d+_/.test(code));
  const hasTechnicalDiscrepancies =
    warningSet.has('discrepancia_lineas')
    || warningSet.has('discrepancia_total')
    || warningSet.has('discrepancia_base_imponible')
    || warningSet.has('discrepancia_iva_importe')
    || warningSet.has('discrepancia_iva_porcentaje');

  if (jobError) {
    warnings.push({
      tone: 'error',
      text: `El proceso automatico registro un error: ${jobError}`,
    });
  }

  if (warningSet.has('doc_ai_fallback')) {
    warnings.push({
      tone: 'warning',
      text: 'La extraccion principal no estuvo disponible y se uso una via de respaldo. Conviene revisar el documento con mas atencion.',
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
      text: 'Falta la contraparte del documento.',
    });
  }

  if (!providerTaxId) {
    warnings.push({
      tone: 'info',
      text: `No se ha detectado el ${taxIdLabel} de la contraparte.`,
    });
  } else if (!isValidTaxId(providerTaxId)) {
    warnings.push({
      tone: 'warning',
      text: `El ${taxIdLabel} de la contraparte parece invalido: ${invoice.proveedor_cif}.`,
    });
  }

  if (companyTaxId && !isValidTaxId(companyTaxId)) {
    warnings.push({
      tone: 'info',
      text: `El ${taxIdLabel} de la empresa asociada parece dudoso: ${invoice.cliente_cif}.`,
    });
  }

  if (base != null && tax != null && total != null) {
    const delta = Math.abs(base + tax - total);
    if (delta > 0.02) {
      warnings.push({
        tone: 'warning',
        text: `Los importes no cuadran: base (${base.toFixed(2)}) + ${taxLabel} (${tax.toFixed(2)}) no coincide con el total (${total.toFixed(2)}).`,
      });
    }
  }

  if (Array.isArray(invoice.lineas) && invoice.lineas.length > 0 && base != null) {
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
      text: 'No se han detectado lineas de factura. Puedes anadirlas manualmente si te hacen falta.',
    });
  }

  if (totalsAreCoherent && hasTechnicalDiscrepancies) {
    warnings.push({
      tone: 'info',
      text: 'Los importes finales ya cuadran. El sistema ha comparado varias vias de extraccion y se ha quedado con la combinacion mas consistente.',
    });
  }

  if (linesMatchBase && hasAutomaticCorrections) {
    warnings.push({
      tone: 'info',
      text: 'El detalle de lineas ya cuadra con la base imponible. Se han aplicado ajustes automaticos sobre la tabla detectada.',
    });
  }

  return warnings;
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
      description="Estas alertas se generan automaticamente para ayudarte a detectar posibles errores."
      items={warnings.map((warning) => warning.text)}
      footer="Si hace falta, puedes corregirlos desde Editar datos."
      compact
    />
  );
}
