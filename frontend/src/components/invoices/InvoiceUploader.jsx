import { useEffect, useMemo, useRef, useState } from 'react';
import { uploadInvoices } from '../../services/invoiceService';
import { isValidFileSize, isValidFileType } from '../../utils/validators';
import InfoPopover from '../common/InfoPopover';
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

export default function InvoiceUploader({ company, onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);
  const [files, setFiles] = useState([]);
  const [channel, setChannel] = useState('web');
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [capturedPhoto, setCapturedPhoto] = useState(null);
  const inputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const cameraSupported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;

  const totalSize = useMemo(
    () => files.reduce((sum, file) => sum + file.size, 0),
    [files]
  );

  const failedDocuments = success?.documents?.filter((document) => document.status === 'failed') || [];

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, []);

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

  const stopCameraStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraReady(false);
  };

  const openCamera = async () => {
    if (!cameraSupported) {
      cameraInputRef.current?.click();
      return;
    }

    setError('');
    setCameraError('');
    setCapturedPhoto(null);
    setCameraOpen(true);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraReady(true);
    } catch (cameraErr) {
      setCameraError('No se pudo acceder a la camara. Puedes usar el selector de archivos como alternativa.');
      setCameraReady(false);
    }
  };

  const closeCamera = () => {
    stopCameraStream();
    setCameraOpen(false);
    setCapturedPhoto(null);
    setCameraError('');
  };

  const capturePhoto = async () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;

    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, width, height);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    setCapturedPhoto(dataUrl);
  };

  const confirmCapturedPhoto = async () => {
    if (!capturedPhoto) return;

    const response = await fetch(capturedPhoto);
    const blob = await response.blob();
    const timestamp = Date.now();
    const file = new File([blob], `camera-${timestamp}.jpg`, {
      type: 'image/jpeg',
      lastModified: timestamp,
    });

    addFiles([file], 'mobile_camera');
    closeCamera();
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
    setUploadProgress(0);

    try {
      const result = await uploadInvoices(files, {
        companyId: company.id,
        channel,
        onProgress: setUploadProgress,
      });
      setSuccess(result);
      setFiles([]);
      onUploaded?.(result);
    } catch (err) {
      setError(err.response?.data?.message || 'Error al subir los documentos');
    } finally {
      setUploading(false);
      setUploadProgress(0);
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

      {error && (
        <StatusPanel
          tone="error"
          eyebrow="Carga fallida"
          title="No se pudo registrar el lote"
          description={error}
          compact
        />
      )}

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
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
              className="btn-primary justify-center"
              disabled={uploading}
            >
              Seleccionar archivos
            </button>
            <button
              type="button"
              onClick={openCamera}
              className="btn-secondary justify-center"
              disabled={uploading}
            >
              Abrir camara
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                Archivos preparados
              </p>
              <p className="mt-2 text-sm text-slate-500">
                El lote manda. Revisa aqui lo esencial antes de procesarlo.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <InfoPopover
                title="Informacion del lote"
                description="Estos datos resumen el bloque actual antes de enviarlo a procesamiento."
                items={[
                  `Empresa: ${company?.nombre || 'Sin empresa activa'}`,
                  `Canal: ${CHANNEL_LABELS[channel] || 'Archivos web'}`,
                  `Documentos: ${files.length}`,
                  `Tamano total: ${formatSize(totalSize)}`,
                ]}
              />

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
          </div>

          {files.length > 0 ? (
            <ul className="mt-4 max-h-[20rem] space-y-2 overflow-y-auto pr-1 sm:max-h-[32rem]">
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
            <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-8 text-center">
              <p className="text-sm font-medium text-slate-700">Aun no has anadido documentos</p>
              <p className="mt-1 text-xs text-slate-500">
                Selecciona archivos o usa la camara para empezar el lote.
              </p>
            </div>
          )}

          <div className="mt-5 flex flex-col gap-3">
            {uploading && (
              <div className="w-full">
                <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                  <span>Subiendo documentos...</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}
            <div className="flex justify-stretch sm:justify-end">
              <button
                type="button"
                onClick={handleUpload}
                className="btn-primary w-full justify-center sm:w-auto"
                disabled={uploading || files.length === 0 || !company?.id}
              >
                {uploading ? `Subiendo (${uploadProgress}%)...` : 'Procesar'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {cameraOpen && (
        <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                Captura con camara
              </p>
              <h3 className="mt-2 text-xl font-bold text-slate-900">
                Saca una foto y anadela al lote
              </h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                La foto entrara en el mismo flujo de subida. Si no queda bien, puedes repetirla antes de anadirla.
              </p>
            </div>

            <button type="button" onClick={closeCamera} className="btn-secondary">
              Cerrar camara
            </button>
          </div>

          {cameraError && (
            <StatusPanel
              tone="warning"
              eyebrow="Camara no disponible"
              title="No se ha podido abrir la camara"
              description={cameraError}
              compact
            />
          )}

          <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-[24px] border border-slate-200 bg-slate-950 p-3 shadow-inner">
              {!capturedPhoto ? (
                <div className="relative overflow-hidden rounded-[18px] bg-black">
                  <video
                    ref={videoRef}
                    className="aspect-[4/3] w-full object-cover"
                    playsInline
                    muted
                  />
                  {!cameraReady && (
                    <div className="absolute inset-0 flex items-center justify-center text-sm font-medium text-white/80">
                      Preparando camara...
                    </div>
                  )}
                </div>
              ) : (
                <img
                  src={capturedPhoto}
                  alt="Captura de factura"
                  className="aspect-[4/3] w-full rounded-[18px] object-cover"
                />
              )}
              <canvas ref={canvasRef} className="hidden" />
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                Flujo movil
              </p>
              <ul className="mt-3 space-y-2 text-sm text-slate-600">
                <li>1. Abre la camara desde el navegador.</li>
                <li>2. Haz la foto con la factura centrada y buena luz.</li>
                <li>3. Repite si no se lee bien.</li>
                <li>4. Anadela al lote y procesa como cualquier documento.</li>
              </ul>

              <div className="mt-5 flex flex-col gap-3">
                {!capturedPhoto ? (
                  <>
                    <button
                      type="button"
                      onClick={capturePhoto}
                      className="btn-primary justify-center"
                      disabled={!cameraReady}
                    >
                      Capturar foto
                    </button>
                    <button
                      type="button"
                      onClick={() => cameraInputRef.current?.click()}
                      className="btn-secondary justify-center"
                    >
                      Usar captura del dispositivo
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={confirmCapturedPhoto}
                      className="btn-success justify-center"
                    >
                      Anadir al lote
                    </button>
                    <button
                      type="button"
                      onClick={() => setCapturedPhoto(null)}
                      className="btn-secondary justify-center"
                    >
                      Repetir foto
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

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
        onChange={(event) => onSelect(event, 'mobile_camera')}
        className="hidden"
      />
    </div>
  );
}
