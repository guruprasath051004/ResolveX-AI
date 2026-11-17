import { describe, it, expect } from 'vitest';

describe('Frontend smoke tests', () => {
  it('App module exports default component', async () => {
    const mod = await import('../App');
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe('function');
  });

  it('Sidebar component is exported', async () => {
    const mod = await import('../components/Sidebar');
    expect(mod.Sidebar).toBeDefined();
  });

  it('API service exports all functions', async () => {
    const api = await import('../services/api');
    const expected = [
      'login', 'logout', 'runAgentChat', 'getDashboardStats', 'getOperationalInsights', 'getIncidents',
      'getApprovals', 'approveRequest', 'rejectRequest', 'getAssets',
      'getSLAPolicies', 'getSLABreaches', 'getSLATrends', 'getMCPStatus', 'getMCPMetrics', 'getMCPCalls',
      'getAgentRuns', 'getAgentRunMetrics', 'getAgentRunDetail', 'getIncidentExecutionTimeline',
      'getKnowledgeDocs', 'getKnowledgeStats', 'getKnowledgeDoc', 'getKnowledgeChunks',
      'evaluateKnowledgeRetrieval', 'uploadKnowledgeDoc', 'deleteKnowledgeDoc', 'reindexKnowledge',
      'getEmployeeDashboard', 'getEmployeeTickets', 'getEmployeeTicket',
      'addEmployeeTicketComment', 'reopenEmployeeTicket', 'submitEmployeeResolutionFeedback',
      'createEmployeeServiceRequest', 'getEmployeeApprovals', 'updateEmployeeProfile',
      'markEmployeeNotificationRead', 'createAnnouncement', 'setAccessToken',
    ];
    for (const fn of expected) {
      expect(api).toHaveProperty(fn);
      expect(typeof (api as any)[fn]).toBe('function');
    }
  });

  it('All page components are importable', async () => {
    const pages = [
      'LoginPage', 'EmployeeHomePage', 'EmployeeChatPage', 'DashboardPage',
      'IncidentsPage', 'ApprovalsPage', 'CommandCenterPage',
      'MCPMonitorPage', 'SLAPage', 'AssetsPage', 'KnowledgePage',
    ];
    for (const page of pages) {
      const mod = await import(`../pages/${page}`);
      expect(mod[page]).toBeDefined();
    }
  });
});

