import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DashboardPage } from '../pages/DashboardPage';
import { SLAPage } from '../pages/SLAPage';
import {
  DashboardStats,
  getDashboardStats,
  getOperationalInsights,
  getSLABreaches,
  getSLAPolicies,
  getSLATrends,
  User,
} from '../services/api';

vi.mock('../services/api', () => ({
  getDashboardStats: vi.fn(),
  getOperationalInsights: vi.fn(),
  getSLABreaches: vi.fn(),
  getSLAPolicies: vi.fn(),
  getSLATrends: vi.fn(),
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
    CartesianGrid: Chart,
    LineChart: Chart,
    Line: Chart,
  };
});

const user: User = {
  id: 1,
  email: 'admin@resolvex.ai',
  role: 'administrator',
  access_token: 'test-token',
};

const dashboardStats: DashboardStats = {
  total_incidents: 12,
  assigned_incidents: 2,
  unassigned_incidents: 1,
  open_incidents: 4,
  in_progress_incidents: 3,
  resolved_incidents: 5,
  critical_incidents: 1,
  approaching_sla_count: 2,
  pending_approvals_count: 1,
  average_resolution_time_min: 42,
  sla_compliance_pct: 80,
  sla_response_compliance_pct: 90,
  sla_resolution_compliance_pct: 70,
  sla_response_sample_count: 10,
  sla_resolution_sample_count: 10,
  sla_compliance_sample_count: 20,
  ai_automation_rate_pct: 60,
  ai_automation_sample_count: 5,
  ai_automation_definition: 'Completed linked agent runs.',
  active_agents_count: 1,
  priority_distribution: [{ name: 'P1 Critical', value: 1 }],
  category_breakdown: [{ name: 'Network', value: 4 }],
  status_distribution: [{ name: 'Open', value: 4 }],
  team_workload: [{ team: 'Network', active_incidents: 3 }],
  trend_chart: [{ date: '2026-11-14', incidents: 2, resolved: 1 }],
  trend_date_range: { start_date: '2026-11-14', end_date: '2026-11-14' },
  applied_date_range: { start_date: '2026-11-14', end_date: '2026-11-14' },
  activity_timeline: [],
  recent_agent_runs: [],
  sla_breaches: [],
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('metrics page integration', () => {
  it('applies the selected date range to dashboard metrics and insights', async () => {
    vi.mocked(getDashboardStats).mockResolvedValue(dashboardStats);
    vi.mocked(getOperationalInsights).mockResolvedValue({
      source: 'database-rules',
      generated_at: '2026-11-14T00:00:00Z',
      date_range: { start_date: '2026-11-14', end_date: '2026-11-14' },
      insights: [{
        key: 'recurring-category-network',
        kind: 'recurrence',
        severity: 'warning',
        title: 'Recurring category: Network',
        explanation: '4 incidents in this date range share this category.',
        recommendation: 'Review the common causes and existing runbook.',
        evidence: { incident_count: 4 },
      }],
    });

    render(<DashboardPage currentUser={user} />);

    expect(await screen.findByText('Recurring category: Network')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    await waitFor(() => {
      expect(getDashboardStats).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(String),
      );
    });

    fireEvent.change(screen.getByLabelText('Dashboard start date'), {
      target: { value: '2026-11-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply / Refresh' }));

    await waitFor(() => {
      expect(getDashboardStats).toHaveBeenLastCalledWith('2026-11-01', expect.any(String));
      expect(getOperationalInsights).toHaveBeenLastCalledWith('2026-11-01', expect.any(String));
    });
  });

  it('shows a dashboard error instead of presenting missing metrics as zero', async () => {
    vi.mocked(getDashboardStats).mockRejectedValue(new Error('Dashboard request failed.'));
    vi.mocked(getOperationalInsights).mockResolvedValue({
      source: 'database-rules',
      generated_at: '2026-11-14T00:00:00Z',
      date_range: { start_date: '2026-11-14', end_date: '2026-11-14' },
      insights: [],
    });

    render(<DashboardPage currentUser={user} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Dashboard request failed.');
    expect(screen.queryByText('Total Incidents')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry dashboard' })).toBeInTheDocument();
  });

  it('renders configured SLA targets, real compliance samples, and active deadline risks', async () => {
    vi.mocked(getSLAPolicies).mockResolvedValue([{
      id: 1,
      name: 'Critical Severity (P1)',
      priority_code: 'P1',
      response_minutes: 15,
      resolution_minutes: 60,
      response_compliance_pct: 90,
      response_sample_count: 10,
      resolution_compliance_pct: 80,
      resolution_sample_count: 5,
      compliance_rate_pct: 86.7,
      sample_count: 5,
      status: 'At Risk',
    }]);
    vi.mocked(getSLABreaches).mockResolvedValue([{
      incident_id: 7,
      ticket_id: 'INC-000007',
      priority: 'critical',
      priority_code: 'P1',
      status: 'investigating',
      response_due_at: '2026-11-14T11:00:00Z',
      resolution_due_at: '2026-11-14T12:00:00Z',
      response_minutes_remaining: -10,
      resolution_minutes_remaining: 20,
      response_risk: 'breached',
      resolution_risk: 'at_risk',
      risk: 'breached',
      deadline_type: 'response',
      minutes_remaining: -10,
      escalation_eligible: true,
      escalation_reason: 'Response deadline missed.',
    }]);
    vi.mocked(getSLATrends).mockResolvedValue({
      date_range: { start_date: '2026-10-16', end_date: '2026-11-14' },
      trend: [{
        date: '2026-11-14',
        response_compliance_pct: 90,
        resolution_compliance_pct: 80,
        response_sample_count: 10,
        resolution_sample_count: 5,
        by_priority: {
          P1: {
            response_compliance_pct: 90,
            resolution_compliance_pct: 80,
            response_sample_count: 10,
            resolution_sample_count: 5,
          },
          P2: {
            response_compliance_pct: null,
            resolution_compliance_pct: null,
            response_sample_count: 0,
            resolution_sample_count: 0,
          },
          P3: {
            response_compliance_pct: null,
            resolution_compliance_pct: null,
            response_sample_count: 0,
            resolution_sample_count: 0,
          },
          P4: {
            response_compliance_pct: null,
            resolution_compliance_pct: null,
            response_sample_count: 0,
            resolution_sample_count: 0,
          },
        },
      }],
    });

    render(<SLAPage />);

    expect(await screen.findByText('Critical Severity (P1)')).toBeInTheDocument();
    expect(screen.getByText('15 min')).toBeInTheDocument();
    expect(screen.getByText('60 min')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument();
    expect(screen.getByText('INC-000007')).toBeInTheDocument();
    expect(screen.getByText('Eligible for policy review')).toBeInTheDocument();
    expect(getSLABreaches).toHaveBeenCalledWith({ windowMinutes: 60 });
    expect(getSLATrends).toHaveBeenCalledWith(expect.any(String), expect.any(String));
  });
});
