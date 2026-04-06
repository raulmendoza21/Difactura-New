import LoginForm from '../components/auth/LoginForm';
import logo from '../assets/logo.png';

export default function Login() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md animate-slide-up">
        <div className="text-center mb-8">
          <img src={logo} alt="Difactura" className="h-14 w-auto mx-auto mb-4 object-contain" />
          <p className="text-slate-500 text-sm mt-1">Gestion inteligente de facturas</p>
        </div>
        <div className="card p-8">
          <h2 className="text-lg font-semibold text-slate-800 mb-6">Iniciar sesion</h2>
          <LoginForm />
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">Acceso seguro al entorno documental</p>
      </div>
    </div>
  );
}
