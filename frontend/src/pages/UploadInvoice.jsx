import { useNavigate } from 'react-router-dom';
import StatusPanel from '../components/common/StatusPanel';
import InvoiceUploader from '../components/invoices/InvoiceUploader';

export default function UploadInvoice() {
  const navigate = useNavigate();

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Subir factura</h1>
        <p className="text-sm text-slate-500 mt-1">
          Sube un PDF o una imagen para extraer datos automaticamente y revisarlos antes de validar.
        </p>
      </div>

      <StatusPanel
        tone="warning"
        eyebrow="Importante"
        title="Revision asistida, no automatizacion ciega"
        description="La IA ayuda a detectar campos e importes, pero la ultima decision sigue siendo tuya. Siempre podras revisar el documento original y corregir lo que haga falta."
        items={[
          'La primera carga del dia puede tardar algo mas si el modelo local estaba en reposo.',
          'Si la factura viene incompleta o dudosa, veras avisos claros en la pantalla de revision.',
        ]}
        compact
      />

      <InvoiceUploader
        onUploaded={(result) => {
          if (result?.factura?.id) {
            setTimeout(() => navigate(`/invoices/review/${result.factura.id}`), 1500);
          }
        }}
      />
    </div>
  );
}
