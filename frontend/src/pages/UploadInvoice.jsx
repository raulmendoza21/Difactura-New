import { Link, useNavigate } from 'react-router-dom';
import StatusPanel from '../components/common/StatusPanel';
import CompanySelector from '../components/companies/CompanySelector';
import InvoiceUploader from '../components/invoices/InvoiceUploader';
import { useAuth } from '../hooks/useAuth';
import { useCompanies } from '../hooks/useCompanies';

const CAPTURE_OPTIONS = [
  'PDF',
  'Imagen',
  'Movil',
  'Lotes',
];

export default function UploadInvoice() {
  const navigate = useNavigate();
  const { selectedCompany, setSelectedCompany, clearSelectedCompany, isEmpresaUser } = useAuth();
  const { companies, loading: companiesLoading } = useCompanies();

  const handleCompanyChange = (event) => {
    const companyId = Number(event.target.value);

    if (!companyId) {
      clearSelectedCompany();
      return;
    }

    const company = companies.find((item) => item.id === companyId);
    if (company) {
      setSelectedCompany(company);
    }
  };

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

          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[360px]">
            <Link to="/invoices" className="btn-primary justify-center text-center">
              Abrir bandeja documental
            </Link>
            {!isEmpresaUser && (
              <Link to="/dashboard" className="btn-secondary justify-center text-center">
                Volver al centro operativo
              </Link>
            )}
          </div>
        </div>
      </section>

      {!isEmpresaUser && !selectedCompany && (
        <StatusPanel
          tone="warning"
          eyebrow="Empresa requerida"
          title="Selecciona una empresa cliente antes de procesar"
          description="El lote documental se asociara a la empresa activa que elijas aqui o en la barra superior."
          compact
        />
      )}

      {!isEmpresaUser && (
        <CompanySelector
          companies={companies}
          value={selectedCompany?.id || ''}
          onChange={handleCompanyChange}
          loading={companiesLoading}
        />
      )}

      {isEmpresaUser && selectedCompany && (
        <StatusPanel
          tone="info"
          eyebrow="Tu empresa"
          title={selectedCompany.nombre}
          description="Los documentos subidos se asociaran automaticamente a tu empresa."
          compact
        />
      )}

      <InvoiceUploader
        company={selectedCompany}
        onUploaded={(result) => {
          if (isEmpresaUser) {
            // Empresa users always go to invoice list
            setTimeout(() => navigate('/invoices'), 1200);
          } else if (result?.summary?.accepted === 1) {
            const firstAccepted = result.documents?.find((document) => document.status === 'queued');
            if (firstAccepted?.factura?.id) {
              setTimeout(() => navigate(`/invoices/review/${firstAccepted.factura.id}`), 1200);
            }
          } else if (result?.summary?.accepted > 1) {
            setTimeout(() => navigate('/invoices'), 1200);
          }
        }}
      />
    </div>
  );
}
