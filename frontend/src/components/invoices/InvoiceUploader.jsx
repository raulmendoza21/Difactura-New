import { useRef, useState } from 'react';
import { uploadInvoice } from '../../services/invoiceService';
import { isValidFileSize, isValidFileType } from '../../utils/validators';
import StatusPanel from '../common/StatusPanel';

export default function InvoiceUploader({ onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedFileName, setSelectedFileName] = useState('');
  const inputRef = useRef(null);

  const handleFile = async (file) => {
    setError('');
    setSuccess('');
    setSelectedFileName(file?.name || '');

    if (!isValidFileType(file)) {
      setError('Formato no soportado. Usa PDF, JPG, PNG o TIFF.');
      return;
    }

    if (!isValidFileSize(file)) {
      setError('El archivo supera los 10 MB.');
      return;
    }

    setUploading(true);

    try {
      const result = await uploadInvoice(file);
      setSuccess(`Factura subida correctamente (ID: ${result.factura?.id || '-'})`);
      onUploaded?.(result);
    } catch (err) {
      setError(err.response?.data?.message || 'Error al subir la factura');
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onSelect = (event) => {
    const file = event.target.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="space-y-4">
      {!uploading && !success && (
        <StatusPanel
          tone="info"
          eyebrow="Carga guiada"
          title="Que ocurrira al subir la factura"
          description="El sistema guardara el documento, lanzara la extraccion automatica y te llevara a una pantalla de revision para confirmar o corregir los datos."
          items={[
            'La primera factura puede tardar mas mientras el modelo local se prepara.',
            'Cuando termine el analisis podras editar cualquier campo antes de validar.',
            'Si el documento tiene dudas, veras avisos automaticos en la revision.',
          ]}
          footer="Formatos admitidos: PDF, JPG, PNG y TIFF. Tamano maximo: 10 MB."
          compact
        />
      )}

      {uploading && (
        <StatusPanel
          tone="progress"
          eyebrow="Procesando"
          title="Subiendo y preparando la factura"
          description={selectedFileName ? `Archivo seleccionado: ${selectedFileName}` : 'Preparando el documento para su revision.'}
          items={[
            'Se esta subiendo el archivo al servidor.',
            'Se lanza la extraccion automatica de datos.',
            'Enseguida se abrira la pantalla de revision con actualizacion automatica.',
          ]}
          footer="No cierres esta pantalla mientras termina la carga inicial."
        />
      )}

      {success && (
        <StatusPanel
          tone="success"
          eyebrow="Factura recibida"
          title="Documento enviado correctamente"
          description="La factura ya esta en el circuito de revision. En unos instantes se abrira la pantalla donde podras revisar y corregir los datos extraidos."
          items={[
            'Si la IA sigue trabajando, veras un estado de progreso claro en la siguiente pantalla.',
            'Podras editar campos, lineas e importes antes de validar.',
          ]}
          compact
        />
      )}

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-2xl p-10 sm:p-16 text-center cursor-pointer transition-all duration-200
          ${dragging ? 'border-blue-400 bg-blue-50/50' : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50/50'}
          ${uploading ? 'pointer-events-none opacity-60' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,.tiff"
          onChange={onSelect}
          className="hidden"
        />

        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 border-3 border-slate-200 border-t-blue-600 rounded-full animate-spin" />
            <p className="text-sm font-medium text-slate-700">Procesando la factura...</p>
            <p className="text-xs text-slate-500">La pantalla de revision se abrira automaticamente al terminar esta fase.</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-14 h-14 bg-blue-50 rounded-2xl flex items-center justify-center">
              <svg className="w-7 h-7 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M7 16a4 4 0 0 1-.88-7.903A5 5 0 1 1 15.9 6L16 6a5 5 0 0 1 1 9.9M15 13l-3-3m0 0-3 3m3-3v12" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-700">
                Arrastra un archivo aqui o <span className="text-blue-600">haz clic para seleccionar</span>
              </p>
              <p className="text-xs text-slate-400 mt-1">PDF, JPG, PNG o TIFF (max. 10 MB)</p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <StatusPanel
          tone="error"
          eyebrow="Carga interrumpida"
          title="No se pudo subir la factura"
          description={error}
          compact
        />
      )}
    </div>
  );
}
