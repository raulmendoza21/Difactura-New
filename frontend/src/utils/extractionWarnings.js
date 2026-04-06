function normalizeWarningCode(code) {
  const value = String(code || '').trim();
  if (!value) return '';

  if (/^linea_\d+_/.test(value)) return 'line_item_adjustment';
  if (value.startsWith('doc_ai_fallback_error')) return 'doc_ai_fallback_error';
  if (value.startsWith('doc_ai_fallback')) return 'doc_ai_fallback';
  if (value.startsWith('discrepancia_')) return 'source_discrepancy';
  if (value === 'region_hint_rescue_applied') return 'region_rescue';
  if (value.startsWith('familia_ticket_')) return 'ticket_interpretation';
  if (value.startsWith('familia_shipping_billing_')) return 'document_role_adjustment';
  if (value.startsWith('familia_company_sale_')) return 'document_role_adjustment';
  if (value.startsWith('familia_rectificativa_')) return 'document_role_adjustment';
  if (value.startsWith('lineas_') || value.startsWith('linea_unica_')) return 'line_item_adjustment';
  if (value.startsWith('base_') || value.startsWith('iva_') || value.startsWith('total_') || value.startsWith('importes_')) {
    return 'amount_adjustment';
  }
  if (value.startsWith('retencion_')) return 'withholding_adjustment';
  if (value.startsWith('proveedor_') || value.startsWith('cliente_')) return 'party_adjustment';
  if (value.startsWith('cif_')) return value.endsWith('_no_valido') ? 'tax_id_validation' : 'party_adjustment';
  if (value.startsWith('numero_factura_')) return 'identity_adjustment';

  return value;
}

const WARNING_MESSAGE_BY_GROUP = {
  doc_ai_fallback: 'La extraccion necesito una via complementaria para resolver partes ambiguas del documento.',
  doc_ai_fallback_error: 'La via complementaria no estuvo disponible y se mantuvo la mejor lectura principal del documento.',
  region_rescue: 'Se reforzo la lectura de zonas concretas del documento para recuperar informacion util.',
  source_discrepancy: 'El sistema comparo varias lecturas del documento y conservo la version mas coherente.',
  line_item_adjustment: 'El detalle de lineas se completo o reconstruyo a partir del documento.',
  amount_adjustment: 'Los importes se ajustaron automaticamente para mantener coherencia documental y matematica.',
  withholding_adjustment: 'La retencion se reviso segun la evidencia disponible en el documento.',
  party_adjustment: 'La identificacion de las partes se reforzo con el contexto del documento.',
  tax_id_validation: 'No se pudo validar con suficiente fiabilidad uno de los identificadores fiscales detectados.',
  identity_adjustment: 'Se revisaron datos de identidad del documento con referencias explicitas del propio contenido.',
  ticket_interpretation: 'El documento se interpreto como ticket o factura simplificada y se priorizo su resumen fiscal frente a datos de pago.',
  document_role_adjustment: 'Los roles documentales se ajustaron segun la estructura detectada en el documento.',
};

export function getNormalizedWarningGroups(warnings = []) {
  const groups = [];
  const seen = new Set();

  warnings.forEach((warningCode) => {
    const group = normalizeWarningCode(warningCode);
    if (!group || seen.has(group)) return;
    seen.add(group);
    groups.push(group);
  });

  return groups;
}

export function getTechnicalWarningMessages(warnings = []) {
  return getNormalizedWarningGroups(warnings)
    .map((group) => WARNING_MESSAGE_BY_GROUP[group])
    .filter(Boolean);
}

export function hasWarningGroup(warnings = [], targetGroup) {
  return getNormalizedWarningGroups(warnings).includes(targetGroup);
}

