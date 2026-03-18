import StatusPanel from '../common/StatusPanel';

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
  const confidence = typeof invoice.confianza_ia === 'number' ? invoice.confianza_ia : null;
  const base = toNumber(invoice.base_imponible);
  const tax = toNumber(invoice.iva_importe);
  const total = toNumber(invoice.total);
  const jobError = invoice.job?.error_message;

  if (jobError) {
    warnings.push({
      tone: 'error',
      text: `El proceso automatico registro un error: ${jobError}`,
    });
  }

  if (confidence != null) {
    if (confidence < 0.75) {
      warnings.push({
        tone: 'warning',
        text: `La confianza de extraccion es baja (${Math.round(confidence * 100)}%). Conviene revisar todos los campos antes de validar.`,
      });
    } else if (confidence < 0.9) {
      warnings.push({
        tone: 'info',
        text: `La confianza de extraccion es media (${Math.round(confidence * 100)}%). Revisa primero importes, fecha y CIF.`,
      });
    }
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
      text: 'Falta el nombre del proveedor.',
    });
  }

  if (invoice.proveedor_cif && !isValidTaxId(invoice.proveedor_cif)) {
    warnings.push({
      tone: 'warning',
      text: `El CIF del proveedor parece invalido: ${invoice.proveedor_cif}.`,
    });
  }

  if (invoice.cliente_cif && !isValidTaxId(invoice.cliente_cif)) {
    warnings.push({
      tone: 'info',
      text: `El CIF del cliente parece dudoso: ${invoice.cliente_cif}.`,
    });
  }

  if (base != null && tax != null && total != null) {
    const delta = Math.abs(base + tax - total);
    if (delta > 0.02) {
      warnings.push({
        tone: 'warning',
        text: `Los importes no cuadran: base (${base.toFixed(2)}) + IVA (${tax.toFixed(2)}) no coincide con el total (${total.toFixed(2)}).`,
      });
    }
  }

  if (!invoice.lineas || invoice.lineas.length === 0) {
    warnings.push({
      tone: 'info',
      text: 'No se han detectado lineas de factura. Puedes anadirlas manualmente si te hacen falta.',
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
