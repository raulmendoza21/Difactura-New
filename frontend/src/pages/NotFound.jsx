import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="text-center animate-fade-in">
        <h1 className="text-7xl font-bold text-slate-200">404</h1>
        <p className="text-lg text-slate-600 mt-3">Página no encontrada</p>
        <p className="text-sm text-slate-400 mt-1">La página que buscas no existe o fue movida</p>
        <Link to="/dashboard" className="btn-primary inline-block mt-6">
          Volver al inicio
        </Link>
      </div>
    </div>
  );
}
