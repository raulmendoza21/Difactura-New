import { Link, useNavigate } from 'react-router-dom';
import StatusPanel from '../components/common/StatusPanel';
import InvoiceUploader from '../components/invoices/InvoiceUploader';
import { useAuth } from '../hooks/useAuth';

const CAPTURE_OPTIONS = [
  'PDF',
  'Imagen',
  'Movil',
  'Lotes',
];

export default function UploadInvoice() {
  const navigate = useNavigate();
  const { selectedCompany } = useAuth();

  return (
    <div className="space-y-6 animate-fade-in">
      <section className="relative overflow-hidden rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-blue-100/70 blur-3xl" />
        <div className="absolute bottom-0 left-16 h-32 w-32 rounded-full bg-emerald-100/60 blur-3xl" />

        <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              Recepcion documental
            </p>
            <h1 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">
              Entrada de facturas
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
              Registra lotes de PDF, imagenes o capturas desde movil y deja cada documento listo
              para entrar en el circuito de procesamiento de la asesoria.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              {CAPTURE_OPTIONS.map((item) => (
                <span
                  key={item}
                  className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[380px]">
            <Link to="/invoices" className="btn-secondary justify-center text-center">
              Abrir bandeja documental
            </Link>
            <Link to="/dashboard" className="btn-secondary justify-center text-center">
              Volver al centro operativo
            </Link>
          </div>
        </div>
      </section>

      {!selectedCompany ? (
        <>
          <StatusPanel
            tone="warning"
            eyebrow="Empresa requerida"
            title="Selecciona una empresa cliente antes de subir"
            description="Necesitamos una empresa activa para asociar correctamente el lote documental."
            items={[
              'Ve al centro operativo y elige la empresa con la que vas a trabajar.',
              'Despues vuelve a esta pantalla para registrar el lote.',
            ]}
            footer="Sin ese contexto no se puede registrar la subida."
          />

          <div className="flex justify-start">
            <Link to="/dashboard" className="btn-secondary">
              Ir al centro operativo
            </Link>
          </div>
        </>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                Empresa activa
              </p>
              <p className="mt-3 text-lg font-semibold text-slate-900">{selectedCompany.nombre}</p>
              <p className="mt-1 text-sm text-slate-500">
                {selectedCompany.cif || 'Sin CIF registrado'}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                Formatos admitidos
              </p>
              <p className="mt-3 text-lg font-semibold text-slate-900">PDF, JPG, PNG y TIFF</p>
              <p className="mt-1 text-sm text-slate-500">
                Hasta 10 MB por archivo y con soporte para lotes.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                Flujo de trabajo
              </p>
              <p className="mt-3 text-lg font-semibold text-slate-900">Subida, proceso y revision</p>
              <p className="mt-1 text-sm text-slate-500">
                El original se conserva y la bandeja documental refleja el estado del lote.
              </p>
            </div>
          </div>

          <InvoiceUploader
            company={selectedCompany}
            onUploaded={(result) => {
              if (result?.summary?.accepted === 1) {
                const firstAccepted = result.documents?.find((document) => document.status === 'queued');
                if (firstAccepted?.factura?.id) {
                  setTimeout(() => navigate(`/invoices/review/${firstAccepted.factura.id}`), 1200);
                }
              } else if (result?.summary?.accepted > 1) {
                setTimeout(() => navigate('/invoices'), 1200);
              }
            }}
          />
        </>
      )}
    </div>
  );
}
