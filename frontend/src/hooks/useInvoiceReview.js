import { useEffect, useRef, useState } from 'react';
import { usePageVisibility } from './usePageVisibility';
import {
  getInvoiceById,
  rejectInvoice,
  reprocessInvoice,
  updateInvoice,
  validateInvoice,
} from '../services/invoiceService';
import { INVOICE_STATES } from '../utils/constants';

const ACTIVE_PROCESSING_STATES = new Set([INVOICE_STATES.SUBIDA, INVOICE_STATES.EN_PROCESO]);
const EDITABLE_STATES = new Set([
  INVOICE_STATES.PENDIENTE_REVISION,
  INVOICE_STATES.PROCESADA_IA,
  INVOICE_STATES.RECHAZADA,
]);
const REPROCESSABLE_STATES = new Set([
  INVOICE_STATES.PENDIENTE_REVISION,
  INVOICE_STATES.PROCESADA_IA,
  INVOICE_STATES.ERROR_PROCESAMIENTO,
  INVOICE_STATES.RECHAZADA,
]);

function toInputValue(value) {
  return value == null ? '' : String(value);
}

function createDraftFromInvoice(invoice) {
  const json = invoice?.documento_json || {};
  const nd = json.normalized_document || {};
  const rawLines = json.lineas || nd.line_items || [];
  return {
    numero_factura: json.numero_factura || '',
    tipo: json.operation_side || 'compra',
    fecha: json.fecha ? String(json.fecha).slice(0, 10) : '',
    proveedor_nombre: json.proveedor || nd.issuer?.name || '',
    proveedor_cif: json.cif_proveedor || nd.issuer?.tax_id || '',
    base_imponible: toInputValue(json.base_imponible),
    iva_porcentaje: toInputValue(json.iva_porcentaje),
    iva_importe: toInputValue(json.iva),
    total: toInputValue(json.total),
    notas: nd.observaciones || json.observaciones || '',
    lineas: rawLines.map((line, i) => ({
      id: `line-${i}-${Math.random().toString(16).slice(2)}`,
      descripcion: line.descripcion || '',
      cantidad: toInputValue(line.cantidad),
      precio_unitario: toInputValue(line.precio_unitario),
      subtotal: toInputValue(line.subtotal ?? line.importe_total ?? line.importe),
    })),
  };
}

function parseNumber(value) {
  if (value === '' || value == null) return null;
  const parsed = Number(String(value).replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : null;
}

function buildUpdatePayload(draft, originalJson) {
  const lines = draft.lineas
    .map((line) => ({
      descripcion: line.descripcion.trim(),
      cantidad: parseNumber(line.cantidad),
      precio_unitario: parseNumber(line.precio_unitario),
      importe: parseNumber(line.subtotal),
    }))
    .filter((line) => line.descripcion || line.cantidad != null || line.precio_unitario != null || line.importe != null);

  return {
    documento_json: {
      ...originalJson,
      numero_factura: draft.numero_factura.trim() || null,
      operation_side: draft.tipo || 'compra',
      fecha: draft.fecha || null,
      proveedor: draft.proveedor_nombre.trim(),
      cif_proveedor: draft.proveedor_cif.trim(),
      base_imponible: parseNumber(draft.base_imponible),
      iva_porcentaje: parseNumber(draft.iva_porcentaje),
      iva: parseNumber(draft.iva_importe),
      total: parseNumber(draft.total),
      lineas: lines,
      normalized_document: {
        ...(originalJson?.normalized_document || {}),
        observaciones: draft.notas.trim() || null,
        line_items: lines,
      },
    },
  };
}

function emptyLine() {
  return {
    id: `line-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    descripcion: '',
    cantidad: '',
    precio_unitario: '',
    subtotal: '',
  };
}

export function useInvoiceReview(id) {
  const isPageVisible = usePageVisibility();
  const loadInvoiceRef = useRef(async () => {});
  const pollTimeoutRef = useRef(null);
  const requestInFlightRef = useRef(false);
  const [invoice, setInvoice] = useState(null);
  const [draft, setDraft] = useState(createDraftFromInvoice(null));
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState('');
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshAt, setLastRefreshAt] = useState(null);
  const [rejectMotivo, setRejectMotivo] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const clearPoll = () => {
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
    };

    const loadInvoice = async (initialLoad = false) => {
      if (requestInFlightRef.current && !initialLoad) {
        return;
      }

      requestInFlightRef.current = true;
      if (initialLoad) setLoading(true);
      setIsRefreshing(true);

      try {
        const data = await getInvoiceById(id);
        if (cancelled) return;

        const nextInvoice = data.factura || data;
        setInvoice(nextInvoice);

        if (!isEditing) {
          setDraft(createDraftFromInvoice(nextInvoice));
        }

        setError('');
        setLastRefreshAt(new Date());

        const isProcessing = ACTIVE_PROCESSING_STATES.has(nextInvoice?.estado);
        clearPoll();

        if (isProcessing && isPageVisible) {
          pollTimeoutRef.current = setTimeout(() => {
            loadInvoice(false);
          }, 2500);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.message || 'No se pudo cargar la factura');
        }
      } finally {
        requestInFlightRef.current = false;
        if (!cancelled) {
          setIsRefreshing(false);
        }
        if (!cancelled && initialLoad) {
          setLoading(false);
        }
      }
    };

    loadInvoiceRef.current = loadInvoice;
    loadInvoice(true);

    return () => {
      cancelled = true;
      clearPoll();
    };
  }, [id, isEditing, isPageVisible]);

  const canAct = [INVOICE_STATES.PENDIENTE_REVISION, INVOICE_STATES.PROCESADA_IA].includes(invoice?.estado);
  const canEdit = EDITABLE_STATES.has(invoice?.estado);
  const canReprocess = REPROCESSABLE_STATES.has(invoice?.estado);
  const isProcessing = ACTIVE_PROCESSING_STATES.has(invoice?.estado);

  const json = invoice?.documento_json || {};
  const fieldConfidence = json.field_confidence || {};
  const operationSide = json.operation_side || 'compra';
  const counterpartyConfidence =
    operationSide === 'venta' ? fieldConfidence.cliente : fieldConfidence.proveedor;
  const counterpartyTaxConfidence =
    operationSide === 'venta' ? fieldConfidence.cif_cliente : fieldConfidence.cif_proveedor;
  const taxLabel = (json.tax_regime || 'IVA').toUpperCase();
  const withholding = json.normalized_document?.withholdings?.[0] || null;

  const handleValidate = async () => {
    setActionLoading('validate');
    setFeedback('');
    try {
      const updated = await validateInvoice(id);
      setInvoice((prev) => ({ ...prev, ...updated, estado: INVOICE_STATES.VALIDADA }));
      setError('');
      setFeedback('Factura validada correctamente.');
    } catch (err) {
      setError(err.response?.data?.message || 'Error al validar');
    } finally {
      setActionLoading('');
    }
  };

  const handleReject = async () => {
    if (!rejectMotivo.trim()) return;
    setActionLoading('reject');
    setFeedback('');
    try {
      const updated = await rejectInvoice(id, rejectMotivo);
      setInvoice((prev) => ({ ...prev, ...updated, estado: INVOICE_STATES.RECHAZADA, notas: rejectMotivo }));
      setDraft((prev) => ({ ...prev, notas: rejectMotivo }));
      setShowReject(false);
      setError('');
      setFeedback('Factura rechazada y anotada correctamente.');
    } catch (err) {
      setError(err.response?.data?.message || 'Error al rechazar');
    } finally {
      setActionLoading('');
    }
  };

  const handleDraftChange = (field, value) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  };

  const handleLineChange = (lineId, field, value) => {
    setDraft((prev) => ({
      ...prev,
      lineas: prev.lineas.map((line) => (line.id === lineId ? { ...line, [field]: value } : line)),
    }));
  };

  const handleAddLine = () => {
    setDraft((prev) => ({ ...prev, lineas: [...prev.lineas, emptyLine()] }));
  };

  const handleRemoveLine = (lineId) => {
    setDraft((prev) => ({
      ...prev,
      lineas: prev.lineas.filter((line) => line.id !== lineId),
    }));
  };

  const handleStartEdit = () => {
    setDraft(createDraftFromInvoice(invoice));
    setIsEditing(true);
    setFeedback('');
    setError('');
  };

  const handleCancelEdit = () => {
    setDraft(createDraftFromInvoice(invoice));
    setIsEditing(false);
    setFeedback('');
    setError('');
  };

  const handleSave = async () => {
    setActionLoading('save');
    setFeedback('');
    try {
      const updated = await updateInvoice(id, buildUpdatePayload(draft, invoice?.documento_json));
      const nextInvoice = updated.factura || updated;
      setInvoice(nextInvoice);
      setDraft(createDraftFromInvoice(nextInvoice));
      setIsEditing(false);
      setFeedback('Cambios guardados correctamente.');
      setError('');
    } catch (err) {
      setError(err.response?.data?.message || 'No se pudieron guardar los cambios');
    } finally {
      setActionLoading('');
    }
  };

  const handleManualRefresh = async () => {
    setFeedback('');
    await loadInvoiceRef.current(false);
  };

  const handleReprocess = async () => {
    setActionLoading('reprocess');
    setFeedback('');
    try {
      const updated = await reprocessInvoice(id);
      const nextInvoice = updated.factura || updated;
      setInvoice(nextInvoice);
      setDraft(createDraftFromInvoice(nextInvoice));
      setIsEditing(false);
      setShowReject(false);
      setRejectMotivo('');
      setError('');
      setFeedback('La factura ha vuelto a la cola de procesamiento.');
      setLastRefreshAt(new Date());
      await loadInvoiceRef.current(false);
    } catch (err) {
      setError(err.response?.data?.message || 'No se pudo relanzar el procesamiento');
    } finally {
      setActionLoading('');
    }
  };

  return {
    invoice,
    draft,
    loading,
    actionLoading,
    error,
    feedback,
    isRefreshing,
    lastRefreshAt,
    rejectMotivo,
    setRejectMotivo,
    showReject,
    setShowReject,
    isEditing,
    confirmAction,
    setConfirmAction,
    canAct,
    canEdit,
    canReprocess,
    isProcessing,
    fieldConfidence,
    operationSide,
    counterpartyConfidence,
    counterpartyTaxConfidence,
    taxLabel,
    withholding,
    handleValidate,
    handleReject,
    handleDraftChange,
    handleLineChange,
    handleAddLine,
    handleRemoveLine,
    handleStartEdit,
    handleCancelEdit,
    handleSave,
    handleManualRefresh,
    handleReprocess,
  };
}
