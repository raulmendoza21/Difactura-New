import { Suspense, lazy, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/auth/ProtectedRoute';
import Navbar from './components/common/Navbar';
import Sidebar from './components/common/Sidebar';
import Footer from './components/common/Footer';
import Login from './pages/Login';
import LoadingSpinner from './components/common/LoadingSpinner';
import { useAuth } from './hooks/useAuth';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const UploadInvoice = lazy(() => import('./pages/UploadInvoice'));
const InvoiceReview = lazy(() => import('./pages/InvoiceReview'));
const InvoiceHistory = lazy(() => import('./pages/InvoiceHistory'));
const NotFound = lazy(() => import('./pages/NotFound'));

function AppLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Overlay movil */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="lg:pl-72 flex flex-col min-h-screen">
        <Navbar onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 animate-fade-in">{children}</main>
        <Footer />
      </div>
    </div>
  );
}

export default function App() {
  const { isAuthenticated, isEmpresaUser } = useAuth();

  const defaultRoute = isEmpresaUser ? '/invoices/upload' : '/dashboard';

  return (
    <Suspense fallback={<LoadingSpinner text="Cargando..." />}>
      <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to={defaultRoute} replace /> : <Login />}
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute asesoriaOnly>
            <AppLayout><Dashboard /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/invoices/upload"
        element={
          <ProtectedRoute roles={['ADMIN', 'CONTABILIDAD', 'EMPRESA_UPLOAD']}>
            <AppLayout><UploadInvoice /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/review-queue"
        element={
          <ProtectedRoute roles={['ADMIN', 'CONTABILIDAD', 'REVISOR']} asesoriaOnly>
            <Navigate to="/invoices" replace />
          </ProtectedRoute>
        }
      />
      <Route
        path="/invoices/review/:id"
        element={
          <ProtectedRoute roles={['ADMIN', 'CONTABILIDAD', 'REVISOR']} asesoriaOnly>
            <AppLayout><InvoiceReview /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/invoices"
        element={
          <ProtectedRoute>
            <AppLayout><InvoiceHistory /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to={defaultRoute} replace />} />
      <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
