import { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/auth/ProtectedRoute';
import Navbar from './components/common/Navbar';
import Sidebar from './components/common/Sidebar';
import Footer from './components/common/Footer';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import UploadInvoice from './pages/UploadInvoice';
import InvoiceReview from './pages/InvoiceReview';
import InvoiceHistory from './pages/InvoiceHistory';
import NotFound from './pages/NotFound';
import { useAuth } from './hooks/useAuth';

function AppLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Overlay móvil */}
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
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login />}
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <AppLayout><Dashboard /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/invoices/upload"
        element={
          <ProtectedRoute roles={['ADMIN', 'CONTABILIDAD']}>
            <AppLayout><UploadInvoice /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/invoices/review/:id"
        element={
          <ProtectedRoute roles={['ADMIN', 'CONTABILIDAD', 'REVISOR']}>
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
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
