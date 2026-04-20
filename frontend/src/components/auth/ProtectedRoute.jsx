import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import LoadingSpinner from '../common/LoadingSpinner';

export default function ProtectedRoute({ children, roles, asesoriaOnly }) {
  const { user, loading, isAuthenticated, isEmpresaUser } = useAuth();

  if (loading) return <LoadingSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  // Block empresa users from asesoria-only routes
  if (asesoriaOnly && isEmpresaUser) {
    return <Navigate to="/invoices/upload" replace />;
  }

  if (roles && !roles.includes(user.rol)) {
    // Empresa users go to upload, asesoria users go to dashboard
    const fallback = isEmpresaUser ? '/invoices/upload' : '/dashboard';
    return <Navigate to={fallback} replace />;
  }

  return children;
}
