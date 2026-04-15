import { formatCurrency } from '../../utils/formatters';
import FieldConfidenceHint from './FieldConfidenceHint';

export default function InvoiceLineItems({ lines = [], confidence = null }) {
  // Normalize field name: AI returns "importe"/"importe_total", UI uses "subtotal"
  // Also filter out empty lines
  const normalizedLines = lines
    .filter((line) => line.descripcion || line.cantidad || line.precio_unitario)
    .map((line) => ({
      ...line,
      subtotal: line.subtotal ?? line.importe_total ?? line.importe ?? null,
    }));
  if (normalizedLines.length === 0) {
    return (
      <div className="card p-6">
        <div className="flex items-center gap-2 mb-2">
          <h3 className="text-base font-semibold text-slate-800">Lineas de factura</h3>
          <FieldConfidenceHint value={confidence} label="Lineas de factura" compact />
        </div>
        <p className="text-sm text-slate-400">No se detectaron lineas de producto</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
        <h3 className="text-base font-semibold text-slate-800">Lineas de factura</h3>
        <FieldConfidenceHint value={confidence} label="Lineas de factura" compact />
      </div>
      <div className="hidden sm:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              <th className="text-left px-5 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Descripcion</th>
              <th className="text-right px-5 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Cantidad</th>
              <th className="text-right px-5 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Precio unit.</th>
              <th className="text-right px-5 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Subtotal</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {normalizedLines.map((line, i) => (
              <tr key={line.id || i} className="hover:bg-slate-50/50">
                <td className="px-5 py-3 text-slate-700">{line.descripcion || '-'}</td>
                <td className="px-5 py-3 text-right text-slate-600">{line.cantidad ?? '-'}</td>
                <td className="px-5 py-3 text-right text-slate-600">{formatCurrency(line.precio_unitario)}</td>
                <td className="px-5 py-3 text-right font-semibold text-slate-800">{formatCurrency(line.subtotal)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="sm:hidden divide-y divide-slate-100">
        {normalizedLines.map((line, i) => (
          <div key={line.id || i} className="p-4">
            <p className="text-sm text-slate-700 font-medium">{line.descripcion || '-'}</p>
            <div className="flex justify-between mt-1 text-xs text-slate-500">
              <span>{line.cantidad ?? '-'} x {formatCurrency(line.precio_unitario)}</span>
              <span className="font-semibold text-slate-800">{formatCurrency(line.subtotal)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
