import StatusPanel from '../common/StatusPanel';

const INPUT_KIND_LABELS = {
  pdf_digital: 'PDF digital',
  pdf_scanned: 'PDF escaneado',
  image_photo: 'Foto',
  image_scan: 'Imagen escaneada',
};

const TEXT_SOURCE_LABELS = {
  digital_text: 'texto nativo',
  ocr: 'OCR',
};

const TECHNICAL_WARNING_LABELS = {
  doc_ai_fallback: 'Se uso una via de respaldo porque la extraccion principal no estuvo disponible.',
  discrepancia_numero_factura: 'Hubo diferencias entre motores al leer el numero de factura.',
  discrepancia_fecha: 'Hubo diferencias entre motores al leer la fecha.',
  discrepancia_proveedor: 'Hubo diferencias entre motores al identificar el emisor.',
  discrepancia_cif_proveedor: 'Hubo diferencias entre motores al identificar el NIF/CIF del emisor.',
  discrepancia_cliente: 'Hubo diferencias entre motores al identificar el receptor.',
  discrepancia_cif_cliente: 'Hubo diferencias entre motores al identificar el NIF/CIF del receptor.',
  discrepancia_base_imponible: 'Hubo diferencias entre motores en la base imponible.',
  discrepancia_iva_porcentaje: 'Hubo diferencias entre motores en el tipo impositivo.',
  discrepancia_iva_importe: 'Hubo diferencias entre motores en la cuota del impuesto.',
  discrepancia_total: 'Hubo diferencias entre motores en el total.',
  discrepancia_lineas: 'Hubo diferencias entre motores en el detalle de lineas.',
  importes_corregidos_con_resumen_fallback: 'Los importes finales se han apoyado en el resumen fiscal del documento.',
  lineas_corregidas_con_fallback: 'El detalle de lineas se ha reordenado con ayuda de la via heuristica.',
  lineas_enriquecidas_con_fallback: 'Se han completado lineas adicionales con la via heuristica.',
  lineas_completadas_con_fallback: 'La via heuristica ha completado lineas que faltaban.',
  lineas_inconsistentes_con_resumen_fiscal: 'El detalle de lineas no coincidia con el resumen fiscal del documento.',
  base_recalculada_por_consistencia: 'La base imponible se ha recalculado por consistencia matematica.',
  base_reconciliada_con_lineas: 'La base imponible se ha reconciliado con la suma de lineas.',
  iva_recalculado_por_consistencia: 'La cuota del impuesto se ha recalculado por consistencia matematica.',
  iva_recalculado_desde_porcentaje: 'La cuota del impuesto se ha recalculado a partir del porcentaje detectado.',
  iva_porcentaje_corregido_por_texto_igic: 'El tipo impositivo se ha corregido usando referencias explicitas a IGIC en el documento.',
  iva_porcentaje_corregido_por_texto_iva: 'El tipo impositivo se ha corregido usando referencias explicitas a IVA en el documento.',
};

function formatPercent(value) {
  return `${Math.round(value * 100)}%`;
}

function formatTechnicalWarnings(warnings = []) {
  const normalizedItems = [];
  const seen = new Set();

  warnings.forEach((warningCode) => {
    if (/^linea_\d+_/.test(warningCode)) {
      warningCode = 'lineas_corregidas_con_fallback';
    } else if (typeof warningCode === 'string' && warningCode.startsWith('doc_ai_fallback')) {
      warningCode = 'doc_ai_fallback';
    }

    const message = TECHNICAL_WARNING_LABELS[warningCode];
    if (!message || seen.has(message)) return;
    seen.add(message);
    normalizedItems.push(message);
  });

  return normalizedItems;
}

export default function ExtractionInsights({ extraction }) {
  if (!extraction) return null;

  const inputKind = extraction.document_input?.input_kind;
  const textSource = extraction.document_input?.text_source;
  const provider = extraction.provider || extraction.normalized_document?.document_meta?.extraction_provider;
  const missingFields = extraction.coverage?.missing_required_fields || [];
  const technicalWarnings = formatTechnicalWarnings(extraction.warnings);
  const confidence = typeof extraction.confianza === 'number'
    ? extraction.confianza
    : extraction.normalized_document?.document_meta?.extraction_confidence;
  const fieldConfidence = extraction.field_confidence || {};

  const items = [];

  if (typeof confidence === 'number') {
    items.push(`Confianza general del documento: ${formatPercent(confidence)}.`);
  }

  if (provider || inputKind || textSource) {
    const channelBits = [
      provider ? `Proveedor: ${provider}` : null,
      inputKind ? `Entrada: ${INPUT_KIND_LABELS[inputKind] || inputKind}` : null,
      textSource ? `Texto base: ${TEXT_SOURCE_LABELS[textSource] || textSource}` : null,
    ].filter(Boolean);

    if (channelBits.length) {
      items.push(channelBits.join(' · '));
    }
  }

  if (missingFields.length > 0) {
    items.push(`Campos prioritarios pendientes o incompletos: ${missingFields.join(', ')}.`);
  }

  const lowTechnicalFields = Object.entries(fieldConfidence)
    .filter(([, value]) => typeof value === 'number' && value < 0.7)
    .map(([field]) => field.replaceAll('_', ' '))
    .slice(0, 5);

  if (lowTechnicalFields.length > 0) {
    items.push(`Campos con menor fiabilidad tecnica: ${lowTechnicalFields.join(', ')}.`);
  }

  if (technicalWarnings.length > 0) {
    items.push(...technicalWarnings);
  }

  const tone = typeof confidence === 'number' && confidence < 0.8 ? 'warning' : 'info';

  return (
    <StatusPanel
      tone={tone}
      eyebrow="Diagnostico tecnico"
      title="Contexto de la extraccion automatica"
      description="Este bloque resume como se ha procesado el documento y que ajustes internos se han aplicado antes de mostrar el resultado final."
      items={items}
      footer="Usalo como ayuda tecnica; los avisos de revision de arriba se centran solo en lo que conviene comprobar antes de validar."
      compact
    />
  );
}
