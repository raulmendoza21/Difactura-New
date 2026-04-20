import CompanySelector from '../companies/CompanySelector';
import { useAuth } from '../../hooks/useAuth';
import { useCompanies } from '../../hooks/useCompanies';

export default function Navbar({ onToggleSidebar }) {
  const { user, advisory, selectedCompany, setSelectedCompany, clearSelectedCompany, logout, isEmpresaUser } = useAuth();
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
    <header className="sticky top-0 z-30 border-b border-slate-200/60 bg-white/80 backdrop-blur-md">
      <div className="flex min-h-16 items-center px-4 sm:px-6 lg:px-8">
        <button
          onClick={onToggleSidebar}
          className="lg:hidden p-2 -ml-1 mr-3 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div className="min-w-0 mr-4">
          {isEmpresaUser ? (
            <>
              <p className="text-sm font-semibold text-slate-800 truncate">
                {selectedCompany?.nombre || 'Mi empresa'}
              </p>
              <p className="text-xs text-slate-500 truncate">
                Portal empresa
              </p>
            </>
          ) : (
            <>
              <p className="text-sm font-semibold text-slate-800 truncate">
                {advisory?.nombre || 'Asesoria'}
              </p>
              <p className="text-xs text-slate-500 truncate">
                {selectedCompany?.nombre || 'Contexto global de asesoria'}
              </p>
            </>
          )}
        </div>

        {!isEmpresaUser && (
          <div className="hidden md:block">
            <CompanySelector
              companies={companies}
              value={selectedCompany?.id || ''}
              onChange={handleCompanyChange}
              loading={companiesLoading}
              variant="topbar"
            />
          </div>
        )}

        <div className="flex-1" />

        <div className="flex items-center gap-3">
          <div className="hidden sm:block text-right">
            <p className="text-sm font-medium text-slate-700">{user?.nombre}</p>
            <p className="text-xs text-slate-400">{user?.email}</p>
          </div>
          <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center shadow-sm">
            <span className="text-white text-sm font-semibold">{user?.nombre?.charAt(0) || 'U'}</span>
          </div>
          <button
            onClick={logout}
            className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all duration-200"
            title="Cerrar sesion"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>

      {!isEmpresaUser && (
        <div className="border-t border-slate-200/60 px-4 py-3 md:hidden sm:px-6">
          <CompanySelector
            companies={companies}
            value={selectedCompany?.id || ''}
            onChange={handleCompanyChange}
            loading={companiesLoading}
            variant="topbar-mobile"
          />
        </div>
      )}
    </header>
  );
}
