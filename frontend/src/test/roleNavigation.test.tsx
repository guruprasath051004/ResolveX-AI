import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { Sidebar } from '../components/Sidebar';
import { DashboardPage } from '../pages/DashboardPage';
import { canAccessPage, getDefaultPage } from '../config/roleNavigation';
import {
  DashboardStats,
  getDashboardStats,
  getOperationalInsights,
  User,
} from '../services/api';

vi.mock('../services/api', () => ({
  getDashboardStats: vi.fn(),
  getOperationalInsights: vi.fn(),
}));

vi.mock('recharts', () => {
  const Chart = () => null;
  return {
    ResponsiveContainer: Chart,
    AreaChart: Chart,
    Area: Chart,
    XAxis: Chart,
    YAxis: Chart,
    Tooltip: Chart,
    Legend: Chart,
    PieChart: Chart,
    Pie: Chart,
    Cell: Chart,
    BarChart: Chart,
    Bar: Chart,
  };
});

const demoStats: DashboardStats = {
  total_incidents: 5,
  assigned_incidents: 1,
  unassigned_incidents: 1,
  open_incidents: 2,
  in_progress_incidents: 1,
  resolved_incidents: 2,
  critical_incidents: 1,
  approaching_sla_count: 0,
  pending_approvals_count: 1,
  active_agents_count: 6,
  average_resolution_time_min: 18,
  sla_compliance_pct: 95,
  sla_response_compliance_pct: 95,
  sla_resolution_compliance_pct: 95,
  sla_response_sample_count: 5,
  sla_resolution_sample_count: 5,
  sla_compliance_sample_count: 10,
  ai_automation_rate_pct: 80,
  ai_automation_sample_count: 5,
  ai_automation_definition: 'Completed linked agent runs.',
  priority_distribution: [{ name: 'High', value: 2 }],
  category_breakdown: [{ name: 'Network', value: 3 }],
  status_distribution: [{ name: 'Open', value: 2 }],
  team_workload: [{ team: 'Network', active_incidents: 1 }],
  trend_chart: [{ date: '2026-01-01', incidents: 2, resolved: 1 }],
  trend_date_range: { start_date: '2026-01-01', end_date: '2026-01-01' },
  applied_date_range: { start_date: '2026-01-01', end_date: '2026-01-01' },
  activity_timeline: [{
    id: 'mcp-1',
    action: 'MCP Tool: check_network_status',
    status: 'success',
    duration_ms: 10,
    time: '2026-01-01T00:00:00Z',
    summary: 'Network check completed',
  }],
  recent_agent_runs: [],
  sla_breaches: [],
};

const demoUser = (role: User['role']): User => ({
  id: 1,
  email: `${role}@resolvex.ai`,
  role,
  access_token: 'test-token',
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('role-specific panels', () => {
  it('routes each role to its intended home panel', () => {
    expect(getDefaultPage('employee')).toBe('home');
    expect(getDefaultPage('support_engineer')).toBe('dashboard');
    expect(getDefaultPage('administrator')).toBe('dashboard');
    expect(canAccessPage('employee', 'dashboard')).toBe(false);
    expect(canAccessPage('employee', 'home')).toBe(true);
  });

  it('shows employee home and AI support in the employee navigation', () => {
    render(
      <Sidebar
        currentPage="chat"
        currentUser={demoUser('employee')}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Employee Home' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'AI Support' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Administrator Dashboard' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Knowledge Base' })).not.toBeInTheDocument();
  });

  it('gives support engineers an operations panel without admin knowledge tools', async () => {
    vi.mocked(getDashboardStats).mockResolvedValue(demoStats);
    vi.mocked(getOperationalInsights).mockResolvedValue({
      source: 'database-rules',
      generated_at: '2026-01-01T00:00:00Z',
      date_range: { start_date: '2026-01-01', end_date: '2026-01-01' },
      insights: [],
    });
    render(<DashboardPage currentUser={demoUser('support_engineer')} />);

    expect(await screen.findByRole('heading', { name: 'Support Operations Dashboard' })).toBeInTheDocument();
    expect(screen.getByText('Open Incidents')).toBeInTheDocument();
    expect(screen.queryByText('Incident Volume & Resolution Trend')).not.toBeInTheDocument();

    render(
      <Sidebar
        currentPage="dashboard"
        currentUser={demoUser('support_engineer')}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: 'Operations Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Incidents Queue' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Knowledge Base' })).not.toBeInTheDocument();
  });

  it('shows administrators the full dashboard and knowledge navigation', async () => {
    vi.mocked(getDashboardStats).mockResolvedValue(demoStats);
    vi.mocked(getOperationalInsights).mockResolvedValue({
      source: 'database-rules',
      generated_at: '2026-01-01T00:00:00Z',
      date_range: { start_date: '2026-01-01', end_date: '2026-01-01' },
      insights: [],
    });
    render(
      <Sidebar
        currentPage="dashboard"
        currentUser={demoUser('administrator')}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: 'Administrator Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Knowledge Base' })).toBeInTheDocument();

    render(<DashboardPage currentUser={demoUser('administrator')} />);
    expect(await screen.findByRole('heading', { name: 'Administrator Dashboard' })).toBeInTheDocument();
    expect(screen.getByText('Incidents Created and Resolved')).toBeInTheDocument();
  });
});
