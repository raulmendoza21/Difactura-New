const { normalizeName } = require('../utils/helpers');
const { INVOICE_STATES } = require('../utils/constants');

function cleanTaxId(value) {
  return String(value || '').replace(/[\s-]/g, '').toUpperCase();
}

function toNumeric(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function clampForDb(value, maxAbs) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.abs(n) > maxAbs ? null : n;
}

function partyFromResult(result, role) {
  const normalized = result?.normalized_document;
  if (role === 'issuer') {
    return {
      name: normalized?.issuer?.name || result?.proveedor || '',
      taxId: normalized?.issuer?.tax_id || result?.cif_proveedor || '',
    };
  }

  return {
    name: normalized?.recipient?.name || result?.cliente || '',
    taxId: normalized?.recipient?.tax_id || result?.cif_cliente || '',
  };
}

function matchesLinkedCompany(party, factura) {
  const partyName = normalizeName(party?.name || '');
  const partyTaxId = cleanTaxId(party?.taxId);
  const companyName = normalizeName(factura?.cliente_nombre || '');
  const companyTaxId = cleanTaxId(factura?.cliente_cif);

  if (partyTaxId && companyTaxId && partyTaxId === companyTaxId) {
    return true;
  }

  return Boolean(partyName && companyName && partyName === companyName);
}

function alignDetectedPartiesWithLinkedCompany(result, factura) {
  if (!result?.normalized_document) {
    return;
  }

  const issuer = partyFromResult(result, 'issuer');
  const recipient = partyFromResult(result, 'recipient');

  if (matchesLinkedCompany(issuer, factura) && (!result.normalized_document.issuer?.name || !result.normalized_document.issuer?.tax_id)) {
    result.normalized_document.issuer.name = factura.cliente_nombre || issuer.name;
    result.normalized_document.issuer.legal_name = factura.cliente_nombre || issuer.name;
    result.normalized_document.issuer.tax_id = factura.cliente_cif || issuer.taxId;
  }

  if (matchesLinkedCompany(recipient, factura) && (!result.normalized_document.recipient?.name || !result.normalized_document.recipient?.tax_id)) {
    result.normalized_document.recipient.name = factura.cliente_nombre || recipient.name;
    result.normalized_document.recipient.legal_name = factura.cliente_nombre || recipient.name;
    result.normalized_document.recipient.tax_id = factura.cliente_cif || recipient.taxId;
  }
}

function setNormalizedParty(target, party) {
  if (!target) {
    return;
  }

  target.name = party?.name || '';
  target.legal_name = party?.name || '';
  target.tax_id = party?.taxId || '';
}

function patchNormalizedParty(target, party) {
  if (!target) {
    return;
  }

  if (!target.name) {
    target.name = party?.name || '';
  }
  if (!target.legal_name) {
    target.legal_name = party?.name || '';
  }
  if (!target.tax_id) {
    target.tax_id = party?.taxId || '';
  }
}

function synchronizeExtractionWithBusinessContext(result, factura, tipoFactura, counterparty) {
  const companyParty = {
    name: factura?.cliente_nombre || '',
    taxId: factura?.cliente_cif || '',
  };

  if (tipoFactura === 'venta') {
    result.proveedor = companyParty.name || result.proveedor || '';
    result.cif_proveedor = companyParty.taxId || result.cif_proveedor || '';
    result.cliente = counterparty?.name || result.cliente || '';
    result.cif_cliente = counterparty?.taxId || result.cif_cliente || '';
  } else {
    result.proveedor = counterparty?.name || result.proveedor || '';
    result.cif_proveedor = counterparty?.taxId || result.cif_proveedor || '';
    result.cliente = companyParty.name || result.cliente || '';
    result.cif_cliente = companyParty.taxId || result.cif_cliente || '';
  }

  if (!result?.normalized_document) {
    return;
  }

  const issuerParty = tipoFactura === 'venta'
    ? companyParty
    : { name: result.proveedor || '', taxId: result.cif_proveedor || '' };
  const recipientParty = tipoFactura === 'venta'
    ? { name: result.cliente || '', taxId: result.cif_cliente || '' }
    : companyParty;

  const normalizedIssuer = result.normalized_document.issuer || {};
  const normalizedRecipient = result.normalized_document.recipient || {};
  const hasResolvedDocumentParties = Boolean(
    (normalizedIssuer.name || normalizedIssuer.tax_id) && (normalizedRecipient.name || normalizedRecipient.tax_id)
  );

  if (hasResolvedDocumentParties && result.normalized_document._fromEngine) {
    patchNormalizedParty(result.normalized_document.issuer, issuerParty);
    patchNormalizedParty(result.normalized_document.recipient, recipientParty);
  } else {
    setNormalizedParty(result.normalized_document.issuer, issuerParty);
    setNormalizedParty(result.normalized_document.recipient, recipientParty);
  }

  if (result.normalized_document.identity) {
    result.normalized_document.identity.invoice_number = result.numero_factura || result.normalized_document.identity.invoice_number || '';
    result.normalized_document.identity.issue_date = result.fecha || result.normalized_document.identity.issue_date || '';
    result.normalized_document.identity.rectified_invoice_number =
      result.rectified_invoice_number || result.normalized_document.identity.rectified_invoice_number || '';
  }

  if (result.normalized_document.classification) {
    result.normalized_document.classification.invoice_side = tipoFactura === 'venta' ? 'emitida' : 'recibida';
    result.normalized_document.classification.operation_kind = tipoFactura === 'venta' ? 'venta' : 'compra';
  }

  if (result.normalized_document.totals) {
    const subtotal = toNumeric(result.base_imponible);
    const taxTotal = toNumeric(result.iva);
    const total = toNumeric(result.total);
    const withholdingTotal = Math.max(0, toNumeric(result.retencion));
    result.normalized_document.totals.subtotal = subtotal;
    result.normalized_document.totals.tax_total = taxTotal;
    result.normalized_document.totals.withholding_total = withholdingTotal;
    result.normalized_document.totals.total = total;
    result.normalized_document.totals.amount_due = total;
  }

  const withholdingTotal = Math.max(0, toNumeric(result.retencion));
  result.normalized_document.withholdings = withholdingTotal > 0
    ? [
        {
          withholding_type: 'IRPF',
          rate: toNumeric(result.retencion_porcentaje),
          taxable_base: toNumeric(result.base_imponible),
          amount: withholdingTotal,
        },
      ]
    : [];
}

function inferInvoiceType(result, factura) {
  const operationSide = result?.operation_side;
  if (operationSide === 'venta' || operationSide === 'compra') {
    return operationSide;
  }

  const normalizedKind = result?.normalized_document?.classification?.operation_kind;
  if (normalizedKind === 'venta') {
    return 'venta';
  }
  if (normalizedKind === 'compra') {
    return 'compra';
  }

  const normalizedSide = result?.normalized_document?.classification?.invoice_side;
  if (normalizedSide === 'emitida') {
    return 'venta';
  }
  if (normalizedSide === 'recibida') {
    return 'compra';
  }

  const matchedRole = result?.company_match?.matched_role;
  if (matchedRole === 'issuer') {
    return 'venta';
  }
  if (matchedRole === 'recipient') {
    return 'compra';
  }

  const issuer = partyFromResult(result, 'issuer');
  const recipient = partyFromResult(result, 'recipient');

  const issuerIsCompany = matchesLinkedCompany(issuer, factura);
  const recipientIsCompany = matchesLinkedCompany(recipient, factura);

  if (issuerIsCompany && !recipientIsCompany) {
    return 'venta';
  }

  if (recipientIsCompany && !issuerIsCompany) {
    return 'compra';
  }

  const fallback = result?.tipo_factura || factura?.tipo || 'compra';
  return (fallback === 'compra' || fallback === 'venta') ? fallback : 'compra';
}

function resolveCounterparty(result, factura, tipoFactura) {
  const issuer = partyFromResult(result, 'issuer');
  const recipient = partyFromResult(result, 'recipient');

  if (tipoFactura === 'venta') {
    if (!matchesLinkedCompany(recipient, factura) && (recipient.name || recipient.taxId)) {
      return recipient;
    }
    if (!matchesLinkedCompany({ name: result?.cliente, taxId: result?.cif_cliente }, factura) && (result?.cliente || result?.cif_cliente)) {
      return { name: result?.cliente || '', taxId: result?.cif_cliente || '' };
    }
    // Name-only fallback: when the model placed our NIF in the wrong field,
    // the recipient matches our company by name but the issuer doesn't — use issuer.
    if (issuer.name && !matchesLinkedCompany({ name: issuer.name, taxId: '' }, factura)) {
      return { name: issuer.name, taxId: '' };
    }
  }

  if (tipoFactura === 'compra') {
    if (!matchesLinkedCompany(issuer, factura) && (issuer.name || issuer.taxId)) {
      return issuer;
    }
    if (!matchesLinkedCompany({ name: result?.proveedor, taxId: result?.cif_proveedor }, factura) && (result?.proveedor || result?.cif_proveedor)) {
      return { name: result?.proveedor || '', taxId: result?.cif_proveedor || '' };
    }
    // Name-only fallback: when the issuer's NIF was swapped with ours but the name
    // correctly identifies a different party, trust the name over the NIF.
    if (issuer.name && !matchesLinkedCompany({ name: issuer.name, taxId: '' }, factura)) {
      return { name: issuer.name, taxId: '' };
    }
  }

  return null;
}

function applyTypeToNormalizedDocument(result, tipoFactura) {
  if (!result?.normalized_document?.classification) {
    return;
  }

  result.normalized_document.classification.invoice_side = tipoFactura === 'venta' ? 'emitida' : 'recibida';
  result.normalized_document.classification.operation_kind = tipoFactura === 'venta' ? 'venta' : 'compra';
}

function shouldRefreshStoredCounterparty(existingSupplier, counterparty, factura) {
  if (!existingSupplier || !counterparty?.name) {
    return false;
  }

  const existingName = normalizeName(existingSupplier.nombre || '');
  const incomingName = normalizeName(counterparty.name || '');
  if (!incomingName || existingName === incomingName) {
    return false;
  }

  const existingLooksLikeCompany = matchesLinkedCompany(
    { name: existingSupplier.nombre, taxId: existingSupplier.cif },
    factura,
  );

  if (existingLooksLikeCompany && !matchesLinkedCompany(counterparty, factura)) {
    return true;
  }

  const genericNames = new Set(['CLIENTE', 'PROVEEDOR', 'EMISOR', 'FACTURA', 'DES', 'MONTES']);
  if (!existingName || genericNames.has(existingName)) {
    return true;
  }

  return false;
}

function buildNormalizedDocumentFromFlat(result) {
  const side = result.operation_side || '';
  const invoiceSide = side === 'venta' ? 'emitida' : side === 'compra' ? 'recibida' : 'desconocida';
  const operationKind = side || 'desconocida';
  const tipo = result.document_type || result.tipo_factura || 'desconocido';
  const subtotal = toNumeric(result.base_imponible);
  const taxTotal = toNumeric(result.iva);
  const total = toNumeric(result.total);
  const withholdingTotal = Math.max(0, toNumeric(result.retencion));
  const taxRate = toNumeric(result.iva_porcentaje);
  const taxRegime = result.tax_regime || 'UNKNOWN';

  const taxBreakdown = subtotal || taxTotal || total
    ? [{ tax_regime: taxRegime, rate: taxRate, taxable_base: subtotal, tax_amount: taxTotal }]
    : [];

  const withholdings = withholdingTotal > 0
    ? [{ withholding_type: 'IRPF', rate: toNumeric(result.retencion_porcentaje), taxable_base: subtotal, amount: withholdingTotal }]
    : [];

  return {
    document_meta: {
      extraction_provider: result.provider || '',
      extraction_method: result.method || '',
      extraction_confidence: result.confianza ?? 0,
      warnings: result.warnings || [],
    },
    classification: {
      document_type: tipo,
      invoice_side: invoiceSide,
      operation_kind: operationKind,
      is_rectificative: String(tipo).includes('rectificativ'),
      is_simplified: String(tipo).includes('simplificad') || String(tipo).includes('ticket'),
    },
    identity: {
      invoice_number: result.numero_factura || '',
      issue_date: result.fecha || '',
      rectified_invoice_number: result.rectified_invoice_number || '',
    },
    issuer: {
      name: result.proveedor || '',
      legal_name: result.proveedor || '',
      tax_id: result.cif_proveedor || '',
    },
    recipient: {
      name: result.cliente || '',
      legal_name: result.cliente || '',
      tax_id: result.cif_cliente || '',
    },
    totals: {
      subtotal,
      tax_total: taxTotal,
      withholding_total: withholdingTotal,
      total,
      amount_due: total,
    },
    tax_breakdown: taxBreakdown,
    withholdings,
    line_items: [],
    payment_info: {},
  };
}

function adaptEngineResultToCurrentModel(engineResult, factura) {
  const result = JSON.parse(JSON.stringify(engineResult || {}));

  if (result.normalized_document) {
    result.normalized_document._fromEngine = true;
  } else {
    result.normalized_document = buildNormalizedDocumentFromFlat(result);
  }

  alignDetectedPartiesWithLinkedCompany(result, factura);
  const tipoFactura = inferInvoiceType(result, factura);
  result.tipo_factura = tipoFactura;
  applyTypeToNormalizedDocument(result, tipoFactura);
  const counterparty = resolveCounterparty(result, factura, tipoFactura);
  synchronizeExtractionWithBusinessContext(result, factura, tipoFactura, counterparty);

  return {
    result,
    tipoFactura,
    counterparty,
  };
}

function buildCurrentPersistencePayload(result, factura, proveedorId) {
  return {
    numero_factura: result.numero_factura || null,
    tipo: result.tipo_factura || factura?.tipo || 'compra',
    fecha: result.fecha || null,
    proveedor_id: proveedorId,
    cliente_id: factura.cliente_id,
    base_imponible: clampForDb(result.base_imponible, 9999999999),
    iva_porcentaje: clampForDb(result.iva_porcentaje, 999),
    iva_importe: clampForDb(result.iva, 9999999999),
    total: clampForDb(result.total, 9999999999),
    confianza_ia: result.confianza,
    estado: INVOICE_STATES.PENDIENTE_REVISION,
    fecha_procesado: new Date(),
  };
}

function buildCurrentAuditDetail(result, jobId, tipoFactura) {
  return {
    job_id: jobId,
    provider: result.provider || null,
    method: result.method || null,
    tipo_factura: tipoFactura,
    confianza: result.confianza ?? null,
    warnings: result.warnings || [],
    document_input: result.document_input || null,
    coverage: result.coverage || null,
    field_confidence: result.field_confidence || {},
    normalized_document: result.normalized_document || null,
    evidence: result.evidence || {},
    decision_flags: result.decision_flags || [],
    company_match: result.company_match || null,
    processing_trace: result.processing_trace || [],
    contract: result.contract || null,
    engine_request: result.engine_request || null,
    operation_side: result.operation_side || null,
    tax_regime: result.tax_regime || null,
  };
}

module.exports = {
  adaptEngineResultToCurrentModel,
  buildCurrentPersistencePayload,
  buildCurrentAuditDetail,
  shouldRefreshStoredCounterparty,
};
