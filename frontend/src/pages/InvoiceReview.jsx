import { useNavigate, useParams } from 'react-router-dom';
import LoadingSpinner from '../components/common/LoadingSpinner';
import StatusPanel from '../components/common/StatusPanel';
import ConfirmDialog from '../components/common/ConfirmDialog';
import InvoiceDetailCard from '../components/invoices/InvoiceDetailCard';
import ExtractionInsights from '../components/invoices/ExtractionInsights';
import FieldConfidenceHint, { getFieldInputClass } from '../components/invoices/FieldConfidenceHint';
import InvoiceLineItems from '../components/invoices/InvoiceLineItems';
import InvoicePreview from '../components/invoices/InvoicePreview';
import ReviewWarnings from '../components/invoices/ReviewWarnings';
import { formatCurrency } from '../utils/formatters';
import { INVOICE_STATES } from '../utils/constants';
import { useInvoiceReview } from '../hooks/useInvoiceReview';

function parseNumber(value) {
  if (value === '' || value == null) return null;
  const parsed = Number(String(value).replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : null;
}

function getProcessingItems(invoice) {
  const items = ['La pantalla se actualiza automaticamente cada pocos segundos.'];

  if (invoice?.estado === INVOICE_STATES.SUBIDA) {
    items.unshift('El documento ya se ha recibido y esta entrando en cola de procesamiento.');
  }

  if (invoice?.estado === INVOICE_STATES.EN_PROCESO) {
    items.unshift('Se estan extrayendo textos, importes y campos clave de la factura.');
  }

  if (invoice?.job?.started_at) {
    items.push('El analisis ya esta en marcha; cuando termine podras revisar y editar los datos.');
  }

  return items;
}

function formatRefreshTime(value) {
  if (!value) return 'pendiente';

  return new Intl.DateTimeFormat('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(value);
}

function getExtractionFieldConfidence(invoice, key) {
  const value = invoice?.documento_json?.field_confidence?.[key];
  return typeof value === 'number' ? value : null;
}

function ReviewFieldLabel({ label, confidence }) {
  return (
    <span className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
      <span>{label}</span>
      <FieldConfidenceHint value={confidence} label={label} compact />
    </span>
  );
}

export default function InvoiceReview() {
  const { id } = useParams();
  const navigate = useNavigate();

  const {
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
  } = useInvoiceReview(id);

  const refreshLabel = formatRefreshTime(lastRefreshAt);
  const showTechnicalInsights =
    typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).get('debug') === '1';

  if (loading) {
    return <LoadingSpinner text="Cargando factura..." />;
  }

  if (error && !invoice) {
    return (
      <div className="text-center py-20">
        <p className="text-red-500 mb-4">{error}</p>
        <button onClick={() => navigate('/invoices')} className="btn-secondary">
          Volver a la bandeja documental
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <button
            onClick={() => navigate('/invoices')}
            className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1 mb-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
            </svg>
            Bandeja documental
          </button>
          <h1 className="text-2xl font-bold text-slate-800">Revision de factura</h1>
        </div>

        <div className="flex flex-wrap gap-2">
          {canEdit && !isEditing && (
            <button onClick={handleStartEdit} disabled={!!actionLoading} className="btn-secondary">
              Editar datos
            </button>
          )}

          {canReprocess && !isEditing && (
            <button onClick={() => setConfirmAction('reprocess')} disabled={!!actionLoading} className="btn-secondary">
              {actionLoading === 'reprocess' ? 'Relanzando...' : 'Reprocesar'}
            </button>
          )}

          {isEditing && (
            <>
              <button onClick={handleCancelEdit} disabled={!!actionLoading} className="btn-secondary">
                Cancelar
              </button>
              <button onClick={handleSave} disabled={!!actionLoading} className="btn-success">
                {actionLoading === 'save' ? 'Guardando...' : 'Guardar cambios'}
              </button>
            </>
          )}

          {canAct && !isEditing && (
            <>
              <button onClick={() => setConfirmAction('validate')} disabled={!!actionLoading} className="btn-success">
                {actionLoading === 'validate' ? 'Validando...' : 'Validar'}
              </button>
              <button onClick={() => setShowReject(true)} disabled={!!actionLoading} className="btn-danger">
                Rechazar
              </button>
            </>
          )}
        </div>
      </div>

      {feedback && (
        <StatusPanel
          tone="success"
          eyebrow="Operacion completada"
          title="Cambios aplicados correctamente"
          description={feedback}
          compact
        />
      )}

      {error && (
        <StatusPanel
          tone="error"
          eyebrow="Operacion no completada"
          title="No se pudo aplicar el cambio"
          description={error}
          compact
        />
      )}

      {isProcessing && (
        <div className="space-y-3">
          <StatusPanel
            tone="progress"
            eyebrow="Procesando"
            title="Extrayendo informacion del documento"
            description="La factura sigue en proceso. Esta pantalla se actualiza automaticamente."
            items={[
              ...getProcessingItems(invoice),
              'Si el modelo local estaba en reposo, el tiempo de respuesta puede aumentar.',
            ]}
            footer={`Ultima comprobacion automatica: ${refreshLabel}.`}
          />
          <div className="flex items-center justify-between gap-3 px-1">
            <p className="text-xs text-slate-500">
              {isRefreshing ? 'Consultando estado de la factura...' : `Estado revisado por ultima vez a las ${refreshLabel}.`}
            </p>
            <button
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              className="btn-secondary text-xs"
            >
              {isRefreshing ? 'Actualizando...' : 'Actualizar ahora'}
            </button>
          </div>
        </div>
      )}

      {invoice?.estado === INVOICE_STATES.ERROR_PROCESAMIENTO && (
        <StatusPanel
          tone="error"
          eyebrow="Error de proceso"
          title="No se pudo completar la extraccion"
          description="La factura ha quedado marcada con error de procesamiento y requiere revision."
          items={[
            invoice?.job?.error_message || 'Revisa los logs del backend y del ai-service para ver el error exacto.',
            'Puedes relanzar el procesamiento desde esta misma pantalla cuando el entorno vuelva a estar disponible.',
          ]}
          footer="Mientras no se reprocesa, esta factura no tendra datos fiables para validar."
        />
      )}

      {isEditing && (
        <StatusPanel
          tone="warning"
          eyebrow="Edicion manual"
          title="Estas corrigiendo los datos extraidos"
          description="Usa el documento original como referencia. Los cambios se guardaran antes de validar."
          items={[
            'Revisa numero de factura, fecha, proveedor, NIF/CIF e importes.',
            'Si faltan lineas, puedes anadirlas manualmente.',
          ]}
          compact
        />
      )}

      {showReject && (
        <div className="card p-5 border-red-200 bg-red-50/30">
          <h3 className="text-sm font-semibold text-slate-800 mb-2">Motivo del rechazo</h3>
          <textarea
            value={rejectMotivo}
            onChange={(event) => setRejectMotivo(event.target.value)}
            placeholder="Indica el motivo del rechazo..."
            className="input-field h-20 resize-none mb-3"
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowReject(false)} className="btn-secondary text-xs">
              Cancelar
            </button>
            <button
              onClick={handleReject}
              disabled={!rejectMotivo.trim() || !!actionLoading}
              className="btn-danger text-xs"
            >
              {actionLoading === 'reject' ? 'Rechazando...' : 'Confirmar rechazo'}
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="space-y-6">
          {!isEditing ? (
            <>
              <InvoiceDetailCard invoice={invoice} />
              <InvoiceLineItems
                lines={invoice?.documento_json?.lineas || invoice?.documento_json?.normalized_document?.line_items || []}
                confidence={getExtractionFieldConfidence(invoice, 'lineas')}
                taxRegime={taxLabel}
              />
            </>
          ) : (
            <>
              <div className="card p-5 space-y-5">
                <div>
                  <h3 className="text-lg font-bold text-slate-800">Datos de la factura</h3>
                  <p className="text-sm text-slate-400 mt-1">
                    Corrige los campos extraidos antes de validar.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <label className="space-y-1">
                    <ReviewFieldLabel label="Numero" confidence={fieldConfidence.numero_factura} />
                    <input
                      className={getFieldInputClass(fieldConfidence.numero_factura)}
                      value={draft.numero_factura}
                      onChange={(event) => handleDraftChange('numero_factura', event.target.value)}
                    />
                  </label>

                  <label className="space-y-1">
                    <ReviewFieldLabel label="Tipo" confidence={null} />
                    <select
                      className="input-field"
                      value={draft.tipo}
                      onChange={(event) => handleDraftChange('tipo', event.target.value)}
                    >
                      <option value="compra">Compra</option>
                      <option value="venta">Venta</option>
                    </select>
                  </label>

                  <label className="space-y-1">
                    <ReviewFieldLabel label="Fecha factura" confidence={fieldConfidence.fecha} />
                    <input
                      type="date"
                      className={getFieldInputClass(fieldConfidence.fecha)}
                      value={draft.fecha}
                      onChange={(event) => handleDraftChange('fecha', event.target.value)}
                    />
                  </label>

                  <div className="space-y-1">
                    <ReviewFieldLabel label="Fecha procesado" confidence={null} />
                    <div className="input-field bg-slate-50 text-slate-500">
                      {invoice?.fecha_procesado ? invoice.fecha_procesado.slice(0, 10) : '-'}
                    </div>
                  </div>

                  <label className="space-y-1">
                    <ReviewFieldLabel label="Emisor" confidence={counterpartyConfidence} />
                    <input
                      className={getFieldInputClass(counterpartyConfidence)}
                      value={draft.proveedor_nombre}
                      onChange={(event) => handleDraftChange('proveedor_nombre', event.target.value)}
                    />
                  </label>

                  <label className="space-y-1">
                    <ReviewFieldLabel label="NIF emisor" confidence={counterpartyTaxConfidence} />
                    <input
                      className={getFieldInputClass(counterpartyTaxConfidence)}
                      value={draft.proveedor_cif}
                      onChange={(event) => handleDraftChange('proveedor_cif', event.target.value)}
                    />
                  </label>

                  <div className="space-y-1">
                    <ReviewFieldLabel label="Empresa asociada" confidence={null} />
                    <div className="input-field bg-slate-50 text-slate-500">
                      {invoice?.empresa_asociada?.nombre || '-'}
                    </div>
                  </div>
                </div>

                <div className="border-t border-slate-100 pt-5">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Importes</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <label className="space-y-1">
                      <ReviewFieldLabel label="Base imponible" confidence={fieldConfidence.base_imponible} />
                      <input
                        className={getFieldInputClass(fieldConfidence.base_imponible)}
                        inputMode="decimal"
                        value={draft.base_imponible}
                        onChange={(event) => handleDraftChange('base_imponible', event.target.value)}
                      />
                    </label>

                    <label className="space-y-1">
                      <ReviewFieldLabel label={`${taxLabel} %`} confidence={fieldConfidence.iva_porcentaje} />
                      <input
                        className={getFieldInputClass(fieldConfidence.iva_porcentaje)}
                        inputMode="decimal"
                        value={draft.iva_porcentaje}
                        onChange={(event) => handleDraftChange('iva_porcentaje', event.target.value)}
                      />
                    </label>

                    <label className="space-y-1">
                      <ReviewFieldLabel label={`${taxLabel} importe`} confidence={fieldConfidence.iva} />
                      <input
                        className={getFieldInputClass(fieldConfidence.iva)}
                        inputMode="decimal"
                        value={draft.iva_importe}
                        onChange={(event) => handleDraftChange('iva_importe', event.target.value)}
                      />
                    </label>

                    <label className="space-y-1">
                      <ReviewFieldLabel label="Total" confidence={fieldConfidence.total} />
                      <input
                        className={getFieldInputClass(fieldConfidence.total)}
                        inputMode="decimal"
                        value={draft.total}
                        onChange={(event) => handleDraftChange('total', event.target.value)}
                      />
                    </label>
                  </div>

                  {withholding && (
                    <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm text-amber-900">
                      <div className="font-medium">
                        {`Retención ${withholding.withholding_type || ''}`.trim()}
                      </div>
                      <div className="mt-1 text-amber-800">
                        {`${Number(withholding.rate || 0).toFixed(2)}% · -${formatCurrency(withholding.amount || 0)}`}
                      </div>
                    </div>
                  )}
                </div>

                <div className="border-t border-slate-100 pt-5">
                  <label className="space-y-1 block">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Notas</span>
                    <textarea
                      className="input-field h-24 resize-none"
                      value={draft.notas}
                      onChange={(event) => handleDraftChange('notas', event.target.value)}
                      placeholder="Observaciones internas o correcciones realizadas..."
                    />
                  </label>
                </div>
              </div>

              <div className="card p-5 space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-semibold text-slate-800">Lineas de factura</h3>
                      <FieldConfidenceHint value={fieldConfidence.lineas} label="Lineas de factura" compact />
                    </div>
                    <p className="text-sm text-slate-400 mt-1">
                      Puedes ajustar cantidades, precios y subtotales.
                    </p>
                  </div>
                  <button onClick={handleAddLine} className="btn-secondary text-sm">
                    Anadir linea
                  </button>
                </div>

                {draft.lineas.length === 0 ? (
                  <p className="text-sm text-slate-400">No hay lineas. Puedes anadirlas manualmente.</p>
                ) : (
                  <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                    {draft.lineas.map((line, index) => (
                      <div
                        key={line.id}
                        className="rounded-2xl border border-slate-200 p-4 space-y-3 bg-slate-50/50"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-slate-700">Linea {index + 1}</p>
                          <button
                            onClick={() => handleRemoveLine(line.id)}
                            className="text-sm text-red-500 hover:text-red-600"
                          >
                            Eliminar
                          </button>
                        </div>

                        <label className="space-y-1 block">
                          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Descripcion</span>
                          <input
                            className="input-field"
                            value={line.descripcion}
                            onChange={(event) => handleLineChange(line.id, 'descripcion', event.target.value)}
                          />
                        </label>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <label className="space-y-1">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Cantidad</span>
                            <input
                              className="input-field"
                              inputMode="decimal"
                              value={line.cantidad}
                              onChange={(event) => handleLineChange(line.id, 'cantidad', event.target.value)}
                            />
                          </label>

                          <label className="space-y-1">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Precio unitario</span>
                            <input
                              className="input-field"
                              inputMode="decimal"
                              value={line.precio_unitario}
                              onChange={(event) => handleLineChange(line.id, 'precio_unitario', event.target.value)}
                            />
                          </label>

                          <label className="space-y-1">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Subtotal</span>
                            <input
                              className="input-field"
                              inputMode="decimal"
                              value={line.subtotal}
                              onChange={(event) => handleLineChange(line.id, 'subtotal', event.target.value)}
                            />
                          </label>
                        </div>

                        <p className="text-xs text-slate-400">
                          Vista previa: {formatCurrency(parseNumber(line.subtotal))}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <div>
          <InvoicePreview document={invoice?.documento} />
        </div>
      </div>

      {!isProcessing && invoice?.estado !== INVOICE_STATES.ERROR_PROCESAMIENTO && (
        <div className="space-y-4">
          <ReviewWarnings invoice={invoice} />
          {showTechnicalInsights && <ExtractionInsights extraction={invoice?.documento_json} />}
        </div>
      )}

      <ConfirmDialog
        open={confirmAction === 'validate'}
        title="Validar factura"
        description="Una vez validada, la factura quedara registrada como correcta. ¿Deseas continuar?"
        confirmLabel="Validar"
        tone="success"
        loading={actionLoading === 'validate'}
        onConfirm={async () => { await handleValidate(); setConfirmAction(null); }}
        onCancel={() => setConfirmAction(null)}
      />

      <ConfirmDialog
        open={confirmAction === 'reprocess'}
        title="Reprocesar factura"
        description="Se descartaran los datos actuales y la factura volvera a la cola de procesamiento. ¿Deseas continuar?"
        confirmLabel="Reprocesar"
        tone="danger"
        loading={actionLoading === 'reprocess'}
        onConfirm={async () => { await handleReprocess(); setConfirmAction(null); }}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}
