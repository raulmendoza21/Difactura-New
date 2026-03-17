import { useEffect, useState } from 'react';
import api from '../../services/api';

export default function InvoicePreview({ document }) {
  const [fileUrl, setFileUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let objectUrl = '';

    async function loadDocument() {
      if (!document?.id) {
        setFileUrl('');
        setError('');
        return;
      }

      setLoading(true);
      setError('');

      try {
        const response = await api.get(`/invoices/documents/${document.id}/file`, {
          responseType: 'blob',
        });

        objectUrl = URL.createObjectURL(response.data);
        setFileUrl(objectUrl);
      } catch {
        setFileUrl('');
        setError('No se pudo cargar la vista previa del documento');
      } finally {
        setLoading(false);
      }
    }

    loadDocument();

    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [document?.id]);

  if (!document) {
    return (
      <div className="card p-8 text-center">
        <svg className="w-12 h-12 text-slate-200 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <p className="text-sm text-slate-400">No hay documento adjunto</p>
      </div>
    );
  }

  const isPdf = document.tipo_mime === 'application/pdf';

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 bg-slate-50/80 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Documento original</h3>
        <span className="badge bg-slate-100 text-slate-500">{document.nombre_archivo || 'archivo'}</span>
      </div>

      <div className="bg-slate-100 flex items-center justify-center min-h-[300px] lg:min-h-[500px]">
        {loading && (
          <p className="text-sm text-slate-500">Cargando vista previa...</p>
        )}

        {!loading && error && (
          <p className="text-sm text-red-500">{error}</p>
        )}

        {!loading && !error && fileUrl && (
          isPdf ? (
            <iframe src={fileUrl} className="w-full h-[500px] lg:h-[700px]" title="PDF Preview" />
          ) : (
            <img src={fileUrl} alt="Factura" className="max-w-full max-h-[700px] object-contain p-4" />
          )
        )}
      </div>
    </div>
  );
}
