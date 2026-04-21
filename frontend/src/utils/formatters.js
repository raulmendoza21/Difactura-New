export function formatCurrency(amount) {
  if (amount == null) return '-';
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency: 'EUR',
  }).format(amount);
}

export function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '-';
  return new Intl.DateTimeFormat('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date);
}

export function formatDateTime(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '-';
  return new Intl.DateTimeFormat('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatPercentage(value, { isRatio = false } = {}) {
  if (value == null) return '-';
  const normalized = isRatio ? value * 100 : value;
  return `${Math.round(normalized)}%`;
}

export function truncateText(text, maxLength = 40) {
  if (!text) return '-';
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

// Identificador propio que mostramos al usuario para cada documento.
// Se deriva del correlativo por empresa cliente cuando esta disponible
// (numeracion limpia por empresa: DOC-000001, DOC-000002...). Si aun no
// existe (facturas creadas antes de la migracion 007), cae al id global
// como fallback para no romper la UI.
export function formatDocumentCode(value) {
  if (value == null || value === '') return 'DOC-?????';
  return `DOC-${String(value).padStart(6, '0')}`;
}

// Helper conveniente: recibe el objeto factura y elige el mejor identificador.
export function getInvoiceCode(invoice) {
  if (!invoice) return 'DOC-?????';
  return formatDocumentCode(invoice.numero_correlativo ?? invoice.id);
}
