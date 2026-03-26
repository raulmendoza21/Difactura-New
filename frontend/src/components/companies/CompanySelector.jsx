export default function CompanySelector({
  companies,
  value,
  onChange,
  loading = false,
  variant = 'panel',
}) {
  if (variant === 'topbar' || variant === 'topbar-mobile') {
    const isMobileVariant = variant === 'topbar-mobile';

    return (
      <div className={isMobileVariant ? 'w-full' : 'min-w-[240px] max-w-[360px]'}>
        <label className="block">
          <span className={`mb-1 block font-semibold uppercase tracking-[0.16em] text-slate-400 ${isMobileVariant ? 'text-[10px]' : 'text-[11px]'}`}>
            Empresa activa
          </span>
          <select
            className={`w-full rounded-xl border border-slate-200 bg-white text-slate-700 shadow-sm transition-colors focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400 ${isMobileVariant ? 'px-3 py-2 text-sm' : 'px-3 py-2.5 text-sm'}`}
            value={value}
            onChange={onChange}
            disabled={loading || companies.length === 0}
          >
            <option value="">Todas las empresas</option>
            {companies.map((company) => (
              <option key={company.id} value={company.id}>
                {company.nombre}{company.cif ? ` - ${company.cif}` : ''}
              </option>
            ))}
          </select>
        </label>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            Empresa cliente
          </p>
          <h2 className="mt-2 text-lg font-semibold text-slate-900">
            Selecciona el contexto de trabajo
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Esta seleccion se usara en la subida de documentos y en la bandeja de revision.
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          {companies.length} disponibles
        </span>
      </div>

      <div className="mt-5">
        <select
          className="input-field"
          value={value}
          onChange={onChange}
          disabled={loading || companies.length === 0}
        >
          <option value="">Selecciona una empresa cliente</option>
          {companies.map((company) => (
            <option key={company.id} value={company.id}>
              {company.nombre}{company.cif ? ` - ${company.cif}` : ''}
            </option>
          ))}
        </select>
      </div>

      {loading && (
        <p className="mt-3 text-sm text-slate-500">
          Cargando empresas cliente...
        </p>
      )}
    </div>
  );
}
