import { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { uploadInvoices } from '../../services/invoiceService';
import { isValidFileSize, isValidFileType } from '../../utils/validators';
import StatusPanel from '../common/StatusPanel';

const CHANNEL_LABELS = {
  web: 'Archivos web',
  mobile_camera: 'Camara movil',
};

function formatSize(bytes) {
  if (!bytes) return '0 KB';
  const units = ['B', 'KB', 'MB'];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function SummaryItem({ label, value, muted = false }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className={`mt-2 text-sm font-semibold ${muted ? 'text-slate-500' : 'text-slate-900'}`}>{value}</p>
    </div>
  );
}

export default function InvoiceUploader({ company, onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);
  const [files, setFiles] = useState([]);
  const [channel, setChannel] = useState('web');
  const inputRef = useRef(null);
  const cameraInputRef = useRef(null);

  const totalSize = useMemo(
    () => files.reduce((sum, file) => sum + file.size, 0),
    [files]
  );

  const acceptedDocuments = success?.documents?.filter((document) => document.status === 'queued') || [];
  const failedDocuments = success?.documents?.filter((document) => document.status === 'failed') || [];

  const addFiles = (incomingFiles, sourceChannel = 'web') => {
    setError('');
    setSuccess(null);

    const nextFiles = [...incomingFiles];
    if (nextFiles.length === 0) {
      return;
    }

    for (const file of nextFiles) {
      if (!isValidFileType(file)) {
        setError(`Formato no soportado en ${file.name}. Usa PDF, JPG, PNG o TIFF.`);
        return;
      }

      if (!isValidFileSize(file)) {
        setError(`El archivo ${file.name} supera los 10 MB.`);
        return;
      }
    }

    setFiles((current) => {
      const seen = new Set(current.map((file) => `${file.name}-${file.size}-${file.lastModified}`));
      const merged = [...current];

      for (const file of nextFiles) {
        const key = `${file.name}-${file.size}-${file.lastModified}`;
        if (!seen.has(key)) {
          merged.push(file);
          seen.add(key);
        }
      }

      return merged;
    });

    setChannel(sourceChannel);
  };

  const removeFile = (fileKeyToRemove) => {
    setFiles((current) =>
      current.filter((file) => `${file.name}-${file.size}-${file.lastModified}` !== fileKeyToRemove)
    );
  };

  const handleUpload = async () => {
    if (!company?.id) {
      setError('Debes seleccionar una empresa cliente antes de subir documentos.');
      return;
    }

    if (files.length === 0) {
      setError('Anade al menos un documento antes de subir.');
      return;
    }

    setError('');
    setSuccess(null);
    setUploading(true);

    try {
      const result = await uploadInvoices(files, { companyId: company.id, channel });
      setSuccess(result);
      setFiles([]);
      onUploaded?.(result);
    } catch (err) {
      setError(err.response?.data?.message || 'Error al subir los documentos');
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    addFiles(Array.from(event.dataTransfer.files || []), 'web');
  };

  const onSelect = (event, sourceChannel = 'web') => {
    addFiles(Array.from(event.target.files || []), sourceChannel);
    event.target.value = '';
  };

  return (
    <div className="space-y-6">
      {uploading && (
        <StatusPanel
          tone="progress"
          eyebrow="Carga en curso"
          title="Recibiendo documentos"
          description={`Se estan registrando ${files.length} documento${files.length !== 1 ? 's' : ''} para ${company?.nombre || 'la empresa seleccionada'}.`}
          items={[
            'Se conserva el archivo original y se crea un registro por documento.',
            'La bandeja documental reflejara el estado del lote en cuanto termine la carga.',
          ]}
          footer="No cierres esta pantalla hasta que finalice la subida."
        />
      )}

      {success && (
        <StatusPanel
          tone={success.summary.failed > 0 ? 'warning' : 'success'}
          eyebrow="Carga completada"
          title="Lote registrado correctamente"
          description={`Se ha creado el lote ${success.batch_id} para ${success.company?.nombre || 'la empresa seleccionada'}.`}
          items={[
            `${success.summary.accepted} documento${success.summary.accepted !== 1 ? 's' : ''} aceptado${success.summary.accepted !== 1 ? 's' : ''}.`,
            success.summary.failed > 0
              ? `${success.summary.failed} documento${success.summary.failed !== 1 ? 's' : ''} no se pudo${success.summary.failed !== 1 ? 'ieron' : ''} registrar en la entrada.`
              : 'Todos los documentos del lote se han registrado correctamente.',
          ]}
          footer="Puedes abrir las revisiones creadas o seguir el lote desde la bandeja documental."
          compact
        />
      )}

      {error && (
        <StatusPanel
          tone="error"
          eyebrow="Carga fallida"
          title="No se pudo registrar el lote"
          description={error}
          compact
        />
      )}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                  Entrada principal
                </p>
                <h2 className="mt-2 text-2xl font-bold text-slate-900">
                  Arrastra o selecciona documentos
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                  Puedes combinar facturas en PDF e imagenes dentro del mismo lote y, si lo necesitas,
                  capturarlas directamente desde movil.
                </p>
              </div>

              <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {files.length} en lote
              </span>
            </div>

            <div
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              onClick={() => inputRef.current?.click()}
              className={`
                mt-6 relative rounded-[24px] border-2 border-dashed px-6 py-12 text-center transition-all duration-200 sm:px-10
                ${dragging ? 'border-blue-400 bg-blue-50/70' : 'border-slate-200 bg-slate-50/60 hover:border-blue-300 hover:bg-blue-50/40'}
                ${uploading ? 'pointer-events-none opacity-60' : 'cursor-pointer'}
              `}
            >
              <div className="mx-auto flex max-w-xl flex-col items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-white shadow-sm">
                  <svg className="h-8 w-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                </div>

                <div>
                  <p className="text-base font-semibold text-slate-900">
                    Suelta aqui los archivos o haz clic para seleccionarlos
                  </p>
                  <p className="mt-2 text-sm text-slate-500">
                    PDF, JPG, PNG o TIFF. Tamano maximo de 10 MB por archivo.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="btn-primary"
                disabled={uploading}
              >
                Seleccionar archivos
              </button>
              <button
                type="button"
                onClick={() => cameraInputRef.current?.click()}
                className="btn-secondary"
                disabled={uploading}
              >
                Capturar desde movil
              </button>
              <button
                type="button"
                onClick={handleUpload}
                className="btn-secondary"
                disabled={uploading || files.length === 0 || !company?.id}
              >
                Registrar lote
              </button>
            </div>
          </div>

          {success && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                    Resultado del lote
                  </p>
                  <h3 className="mt-2 text-lg font-semibold text-slate-900">Accesos rapidos</h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link to="/invoices" className="btn-secondary">
                    Ver bandeja documental
                  </Link>
                  <Link to="/dashboard" className="btn-secondary">
                    Volver al centro operativo
                  </Link>
                </div>
              </div>

              {acceptedDocuments.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {acceptedDocuments.map((document) => (
                    <li
                      key={`${document.factura?.id}-${document.original_name}`}
                      className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-800">{document.original_name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          Factura #{document.factura?.id} - {formatSize(document.size_bytes)}
                        </p>
                      </div>
                      <Link to={`/invoices/review/${document.factura?.id}`} className="btn-secondary">
                        Abrir revision
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
              Resumen del lote
            </p>

            <div className="mt-4 grid gap-3">
              <SummaryItem label="Empresa" value={company?.nombre || 'Sin empresa'} muted={!company?.nombre} />
              <SummaryItem label="Documentos" value={`${files.length}`} />
              <SummaryItem label="Tamano total" value={formatSize(totalSize)} />
              <SummaryItem label="Canal" value={CHANNEL_LABELS[channel] || 'Archivos web'} />
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Archivos preparados
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  Revisa el lote antes de registrarlo.
                </p>
              </div>

              {files.length > 0 && (
                <button
                  type="button"
                  onClick={() => setFiles([])}
                  className="text-xs font-semibold text-slate-500 hover:text-slate-700"
                >
                  Vaciar
                </button>
              )}
            </div>

            {files.length > 0 ? (
              <ul className="mt-4 max-h-[22rem] space-y-2 overflow-y-auto pr-1">
                {files.map((file) => {
                  const key = `${file.name}-${file.size}-${file.lastModified}`;
                  return (
                    <li
                      key={key}
                      className="flex items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-800">{file.name}</p>
                        <p className="mt-1 text-xs text-slate-500">{formatSize(file.size)}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(key)}
                        className="text-xs font-semibold text-red-500 hover:text-red-700"
                      >
                        Quitar
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-6 text-center">
                <p className="text-sm font-medium text-slate-700">Aun no has anadido documentos</p>
                <p className="mt-1 text-xs text-slate-500">
                  Selecciona archivos o usa la camara para empezar el lote.
                </p>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
              Que ocurre al registrar
            </p>
            <ul className="mt-4 space-y-3 text-sm text-slate-600">
              <li className="flex gap-3">
                <span className="mt-2 h-2 w-2 rounded-full bg-blue-500" />
                <span>Se conserva el documento original para trazabilidad y revision posterior.</span>
              </li>
              <li className="flex gap-3">
                <span className="mt-2 h-2 w-2 rounded-full bg-blue-500" />
                <span>Cada archivo genera su propio registro documental y entra en el circuito de proceso.</span>
              </li>
              <li className="flex gap-3">
                <span className="mt-2 h-2 w-2 rounded-full bg-blue-500" />
                <span>La bandeja documental te permitira seguir el estado del lote y abrir cada factura.</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {success && failedDocuments.length > 0 && (
        <div className="rounded-2xl border border-red-200 bg-red-50/70 p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-red-500">
            Documentos con incidencia
          </p>
          <ul className="mt-4 space-y-2">
            {failedDocuments.map((document) => (
              <li
                key={`${document.original_name}-${document.size_bytes}`}
                className="rounded-2xl border border-red-100 bg-white/70 px-4 py-3 text-sm text-red-700"
              >
                <p className="font-medium">{document.original_name}</p>
                <p className="mt-1 text-xs">{document.error || 'Error no especificado'}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.tiff"
        multiple
        onChange={(event) => onSelect(event, 'web')}
        className="hidden"
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        onChange={(event) => onSelect(event, 'mobile_camera')}
        className="hidden"
      />
    </div>
  );
}
