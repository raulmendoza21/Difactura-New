export function getTaxRegime(invoice) {
  return (
    invoice?.extraction?.tax_regime ||
    invoice?.extraction?.normalized_document?.tax_breakdown?.[0]?.tax_regime ||
    invoice?.extraction?.normalized_document?.classification?.tax_regime ||
    ''
  );
}

export function getTaxLabel(invoice) {
  const regime = String(getTaxRegime(invoice) || '').toUpperCase();
  if (regime === 'IGIC') return 'IGIC';
  if (regime === 'IVA') return 'IVA';
  return 'Impuesto';
}

export function getTaxIdLabel() {
  return 'NIF/CIF';
}
