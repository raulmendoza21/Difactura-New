import { createContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import * as authService from '../services/authService';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [advisory, setAdvisory] = useState(null);
  const [selectedCompany, setSelectedCompanyState] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const currentUser = authService.getCurrentUser();
    const currentAdvisory = authService.getCurrentAdvisory();
    const currentCompany = authService.getSelectedCompany();

    if (currentUser && authService.getToken()) {
      setUser(currentUser);
      setAdvisory(currentAdvisory);
      setSelectedCompanyState(currentCompany);
    }

    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const data = await authService.login(email, password);
    setUser(data.user);
    setAdvisory(data.advisory);
    setSelectedCompanyState(null);
    return data;
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    setAdvisory(null);
    setSelectedCompanyState(null);
  };

  const navigate = useNavigate();

  useEffect(() => {
    const handleExpired = () => {
      setUser(null);
      setAdvisory(null);
      setSelectedCompanyState(null);
      navigate('/login', { replace: true });
    };

    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, [navigate]);

  const setSelectedCompany = (company) => {
    authService.setSelectedCompany(company);
    setSelectedCompanyState(company);
  };

  const clearSelectedCompany = () => {
    authService.clearSelectedCompany();
    setSelectedCompanyState(null);
  };

  const value = {
    user,
    advisory,
    selectedCompany,
    loading,
    login,
    logout,
    setSelectedCompany,
    clearSelectedCompany,
    isAuthenticated: !!user,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
