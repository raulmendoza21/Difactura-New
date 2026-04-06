import StatusPanel from '../common/StatusPanel';
import { getTechnicalWarningMessages } from '../../utils/extractionWarnings';

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

function formatPercent(value) {
  return `${Math.round(value * 100)}%`;
}

function formatCompanyMatch(companyMatch) {
  if (!companyMatch?.matched_role) return '';
  if (companyMatch.matched_role === 'issuer') {
    return 'La empresa asociada encaja con el emisor documental.';
  }
  if (companyMatch.matched_role === 'recipient') {
    return 'La empresa asociada encaja con el receptor documental.';
  }
  if (companyMatch.matched_role === 'ambiguous') {
    return 'La empresa asociada encaja con ambas partes documentales y puede haber ambiguedad.';
  }
  return '';
}

export default function ExtractionInsights({ extraction }) {
  if (!extraction) return null;

  const inputKind = extraction.document_input?.input_kind;
  const textSource = extraction.document_input?.text_source;
  const provider = extraction.provider || extraction.normalized_document?.document_meta?.extraction_provider;
  const documentType = extraction.normalized_document?.classification?.document_type || '';
  const missingFields = extraction.coverage?.missing_required_fields || [];
  const technicalWarnings = getTechnicalWarningMessages(extraction.warnings);
  const companyMatchText = formatCompanyMatch(extraction.company_match);
  const confidence = typeof extraction.confianza === 'number'
    ? extraction.confianza
    : extraction.normalized_document?.document_meta?.extraction_confidence;
  const fieldConfidence = extraction.field_confidence || {};
  const processingTrace = extraction.processing_trace || [];

  const items = [];
  const optionalLowFields = documentType === 'ticket' || documentType === 'factura_simplificada'
    ? new Set(['cliente', 'cif_cliente', 'base_imponible', 'iva_porcentaje', 'iva'])
    : new Set();

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
    .filter(([field, value]) => typeof value === 'number' && value < 0.7 && !optionalLowFields.has(field))
    .map(([field]) => field.replaceAll('_', ' '))
    .slice(0, 5);

  if (lowTechnicalFields.length > 0) {
    items.push(`Campos con menor fiabilidad tecnica: ${lowTechnicalFields.join(', ')}.`);
  }

  if (technicalWarnings.length > 0) {
    items.push(...technicalWarnings);
  }

  if (companyMatchText) {
    items.push(companyMatchText);
  }

  if (processingTrace.length > 0) {
    processingTrace.slice(0, 3).forEach((step) => {
      if (step?.summary) {
        items.push(step.summary);
      }
    });
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
