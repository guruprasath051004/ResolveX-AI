import React, { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { logout, setAccessToken, User } from './services/api';
import { Sidebar } from './components/Sidebar';
import { LoginPage } from './pages/LoginPage';
import { EmployeeChatPage } from './pages/EmployeeChatPage';
import { DashboardPage } from './pages/DashboardPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { CommandCenterPage } from './pages/CommandCenterPage';
import { MCPMonitorPage } from './pages/MCPMonitorPage';
import { SLAPage } from './pages/SLAPage';
import { AssetsPage } from './pages/AssetsPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { ScenarioLabPage } from './pages/ScenarioLabPage';
import { EmployeeHomePage } from './pages/EmployeeHomePage';
import { AppPage, canAccessPage, getDefaultPage } from './config/roleNavigation';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [currentPage, setCurrentPage] = useState<AppPage>('chat');
  const [selectedIncidentId, setSelectedIncidentId] = useState<number | null>(null);
  const [authNotice, setAuthNotice] = useState<string | null>(null);

  const handleLogin = (user: User) => {
    queryClient.clear();
    setAccessToken(user.access_token);
    setCurrentUser(user);
    const initUrl = new URL(window.location.href);
    const param = initUrl.searchParams.get('incident');
    const valid = param && Number.isInteger(Number(param)) && Number(param) > 0 && Number(param) < 9007199254740990;
    if (valid && canAccessPage(user.role, 'incidents')) {
      setCurrentPage('incidents');
      setSelectedIncidentId(Number(param));
    } else {
      setCurrentPage(getDefaultPage(user.role));
    }
    setAuthNotice(null);
  };

  const clearSession = (notice: string | null) => {
    setAccessToken(null);
    queryClient.clear();
    setCurrentUser(null);
    setCurrentPage('chat');
    setSelectedIncidentId(null);
    setAuthNotice(notice);
  };

  const handleLogout = async () => {
    try {
      await logout();
      clearSession(null);
    } catch {
      clearSession(
        'Signed out on this device, but server-side token revocation failed. The token remains valid until it expires.',
      );
    }
  };

  // Session expiration listener
  useEffect(() => {
    const handleSessionExpired = () => {
      clearSession('Your session expired or was revoked. Please sign in again.');
    };
    window.addEventListener('resolvex:auth-expired', handleSessionExpired);
    return () => window.removeEventListener('resolvex:auth-expired', handleSessionExpired);
  }, []);

  // Redirect if user lacks access to current page
  useEffect(() => {
    if (currentUser && !canAccessPage(currentUser.role, currentPage)) {
      setCurrentPage(getDefaultPage(currentUser.role));
    }
  }, [currentPage, currentUser]);

  // URL hydration and popstate handling – must run before any early return
useEffect(() => {
  // Hydrate from URL on mount (or after login)
  const initUrl = new URL(window.location.href);
  const param = initUrl.searchParams.get('incident');
  if (param) {
    const id = Number(param);
    if (Number.isInteger(id) && id > 0) {
      setSelectedIncidentId(id);
    }
  }
  const onPopState = () => {
    const url = new URL(window.location.href);
    const p = url.searchParams.get('incident');
    if (p) {
      const id = Number(p);
      setSelectedIncidentId(Number.isInteger(id) && id > 0 ? id : null);
    } else {
      setSelectedIncidentId(null);
    }
  };
  window.addEventListener('popstate', onPopState);
  return () => window.removeEventListener('popstate', onPopState);
}, []);

// Not logged in → show login page
if (!currentUser) {
  return (
    <QueryClientProvider client={queryClient}>
      <LoginPage onLoginSuccess={handleLogin} notice={authNotice} />
    </QueryClientProvider>
  );
}

  const activePage = canAccessPage(currentUser.role, currentPage)
    ? currentPage
    : getDefaultPage(currentUser.role);



  const handleNavigate = (page: string, incidentId?: number) => {
    if (incidentId !== undefined) {
      setSelectedIncidentId(incidentId);
      const url = new URL(window.location.href);
      const current = url.searchParams.get('incident');
      if (String(incidentId) !== current) {
        url.searchParams.set('incident', String(incidentId));
        window.history.pushState(null, '', url.toString());
      }
    } else {
      setSelectedIncidentId(null);
      const url = new URL(window.location.href);
      if (url.searchParams.has('incident')) {
        url.searchParams.delete('incident');
        window.history.pushState(null, '', url.toString());
      }
    }
    setCurrentPage(page as AppPage);
  };

  const renderPage = () => {
    switch (activePage) {
      case 'home':
        return <EmployeeHomePage currentUser={currentUser} onNavigate={handleNavigate} />;
      case 'chat':
        return <EmployeeChatPage currentUser={currentUser} onNavigate={handleNavigate} />;
      case 'dashboard':
        return <DashboardPage currentUser={currentUser} onNavigate={handleNavigate} />;
      case 'incidents':
        return (
          <IncidentsPage
            initialIncidentId={selectedIncidentId}
            onClearInitialId={() => setSelectedIncidentId(null)}
            currentUser={currentUser}
          />
        );
      case 'approvals':
        return <ApprovalsPage onNavigate={handleNavigate} />;
      case 'command-center':
        return <CommandCenterPage onNavigate={handleNavigate} currentUser={currentUser} />;
      case 'scenario-lab':
        return <ScenarioLabPage />;
      case 'mcp-monitor':
        return <MCPMonitorPage />;
      case 'sla':
        return <SLAPage />;
      case 'assets':
        return <AssetsPage />;
      case 'knowledge':
        return <KnowledgePage />;
      default:
        return <DashboardPage currentUser={currentUser} onNavigate={handleNavigate} />;
    }
  };

  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen bg-slate-100 overflow-hidden">
        <Sidebar
          currentPage={activePage}
          onNavigate={handleNavigate}
          currentUser={currentUser}
          onLogout={handleLogout}
        />
        <main className="flex-1 overflow-y-auto">
          {renderPage()}
        </main>
      </div>
    </QueryClientProvider>
  );
};

export default App;
