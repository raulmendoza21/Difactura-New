export const INVOICE_STATES = {
  SUBIDA: 'SUBIDA',
  EN_PROCESO: 'EN_PROCESO',
  PROCESADA_IA: 'PROCESADA_IA',
  PENDIENTE_REVISION: 'PENDIENTE_REVISION',
  VALIDADA: 'VALIDADA',
  SINCRONIZADA: 'SINCRONIZADA',
  ERROR_PROCESAMIENTO: 'ERROR_PROCESAMIENTO',
  RECHAZADA: 'RECHAZADA',
};

export const INVOICE_STATE_LABELS = {
  SUBIDA: 'Subida',
  EN_PROCESO: 'En proceso',
  PROCESADA_IA: 'Procesada por IA',
  PENDIENTE_REVISION: 'Pendiente de revision',
  VALIDADA: 'Validada',
  SINCRONIZADA: 'Sincronizada',
  ERROR_PROCESAMIENTO: 'Error de procesamiento',
  RECHAZADA: 'Rechazada',
};

export const INVOICE_STATE_COLORS = {
  SUBIDA: 'bg-slate-100 text-slate-700',
  EN_PROCESO: 'bg-blue-50 text-blue-700',
  PROCESADA_IA: 'bg-indigo-50 text-indigo-700',
  PENDIENTE_REVISION: 'bg-amber-50 text-amber-700',
  VALIDADA: 'bg-emerald-50 text-emerald-700',
  SINCRONIZADA: 'bg-teal-50 text-teal-700',
  ERROR_PROCESAMIENTO: 'bg-red-50 text-red-700',
  RECHAZADA: 'bg-red-50 text-red-700',
};

export const JOB_STATE_LABELS = {
  PENDIENTE: 'En cola',
  EN_PROCESO: 'Procesando',
  COMPLETADO: 'Completado',
  ERROR: 'Con error',
};

export const JOB_STATE_COLORS = {
  PENDIENTE: 'bg-slate-100 text-slate-700',
  EN_PROCESO: 'bg-blue-50 text-blue-700',
  COMPLETADO: 'bg-emerald-50 text-emerald-700',
  ERROR: 'bg-red-50 text-red-700',
};

export const DOCUMENT_CHANNEL_LABELS = {
  web: 'Web',
  mobile: 'Movil',
  camera: 'Camara',
};

export const USER_ROLES = {
  ADMIN: 'ADMIN',
  CONTABILIDAD: 'CONTABILIDAD',
  REVISOR: 'REVISOR',
  LECTURA: 'LECTURA',
};

export const INVOICE_TYPES = {
  COMPRA: 'COMPRA',
  VENTA: 'VENTA',
};

export const INVOICE_TYPE_LABELS = {
  COMPRA: 'Compra',
  VENTA: 'Venta',
  compra: 'Compra',
  venta: 'Venta',
};

export const CONFIDENCE_THRESHOLDS = {
  HIGH: 90,
  MEDIUM: 70,
};

export const MAX_FILE_SIZE = 10 * 1024 * 1024;
export const ALLOWED_FILE_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/tiff'];
