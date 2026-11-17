import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { IncidentsPage } from '../pages/IncidentsPage';
import { CommandCenterPage } from '../pages/CommandCenterPage';
import { ApprovalsPage } from '../pages/ApprovalsPage';
import { DashboardPage } from '../pages/DashboardPage';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  addIncidentComment: vi.fn(),
  claimIncident: vi.fn(),
  executeMcpTool: vi.fn(),
  getAgentRunMetrics: vi.fn().mockResolvedValue({ total_runs: 5, agent_breakdown: [] }),
  getAgentRuns: vi.fn().mockResolvedValue([]),
  getApprovals: vi.fn().mockResolvedValue([]),
  getDashboardStats: vi.fn().mockResolvedValue({
    open_incidents: 2,
    mttr_hours: 1.5,
    sla_compliance_rate: 98.2,
    first_contact_resolution_rate: 85.0,
    incidents_by_priority: [],
    incidents_by_category: [],
    sla_breaches_last_30_days: [],
    sla_breaches: [
      {
        id: 42,
        ticket_id: 'INC-000042',
        title: 'VPN Connection Failure',
        priority: 'high',
        status: 'assigned',
        minutes_remaining: 15,
        due_at: '2026-11-14T03:00:00Z',
      },
    ],
    workload_by_team: [],
  }),
  getEligibleEngineers: vi.fn().mockResolvedValue({ category: '', priority: '', eligible_engineers: [] }),
  getIncident: vi.fn(),
  getIncidentExceptions: vi.fn().mockResolvedValue([]),
  getIncidents: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 }),
  getMCPStatus: vi.fn().mockResolvedValue({ tools: [] }),
  getOperationalInsights: vi.fn().mockResolvedValue([]),
  getSLABreaches: vi.fn().mockResolvedValue([]),
  getSLAPolicies: vi.fn().mockResolvedValue([]),
  getSupportUsers: vi.fn().mockResolvedValue([]),
  getWorkforceEngineers: vi.fn().mockResolvedValue([]),
  investigateIncident: vi.fn(),
  listAssignmentPolicies: vi.fn().mockResolvedValue([]),
  listWorkforceExceptions: vi.fn().mockResolvedValue([]),
  rejectIncidentAssignment: vi.fn(),
  updateAssignmentPolicy: vi.fn(),
  updateIncident: vi.fn(),
}));

const mockIncidentDetail = {
  id: 42,
  ticket_id: 'INC-000042',
  title: 'VPN Connection Failure',
  description: 'Remote engineer cannot connect to global VPN gateway',
  status: 'assigned',
  priority: 'high',
  category: 'network',
  assigned_team: 'Network Operations',
  assigned_to: { id: 3, name: 'Support Engineer', email: 'support@resolvex.ai' },
  lock_version: 4,
  asset: null,
  created_at: '2026-11-14T01:00:00',
  updated_at: '2026-11-14T01:00:00',
  first_response_at: null,
  resolved_at: null,
  response_due_at: null,
  resolution_due_at: null,
  resolution_summary: null,
  sla: { risk: 'at_risk', minutes_remaining: 25, breached: false },
  employee: {
    id: 1,
    name: 'Alex Employee',
    email: 'alex@example.test',
    department: 'Sales',
    assets: [],
  },
  history: [],
  comments: [],
  related_incidents: [],
  agent_runs: [],
  mcp_calls: [],
};

  const mockEngineers = [
    {
      id: 101,
      email: 'marcus@resolvex.ai',
      full_name: 'Marcus Brody',
      department: null,
      team: 'Network Operations',
      availability_status: 'available' as const,
      is_available: true,
      availability_reason: '',
      skills: ['network', 'vpn', 'cisco'],
      current_workload: 2,
      max_active_tickets: 5,
      working_schedule: '08:00 - 16:00 UTC',
      notes: null,
      is_simulated: true,
    },
    {
      id: 102,
      email: 'elena@resolvex.ai',
      full_name: 'Elena Rostova',
      department: null,
      team: 'Identity & Access',
      availability_status: 'on_leave' as const,
      is_available: false,
      availability_reason: 'Leave',
      skills: ['okta', 'active_directory'],
      current_workload: 0,
      max_active_tickets: 5,
      working_schedule: '09:00 - 17:00 UTC',
      notes: null,
      is_simulated: true,
    },
  ];


const mockExceptions = [
  {
    id: 901,
    incident_id: 42,
    exception_type: 'engineer_on_leave',
    severity: 'warning',
    attempted_engineer: 'Elena Rostova',
    resolved_engineer: 'Marcus Brody',
    action_taken: 'Reassigned to next qualified active specialist',
    reason: 'Primary engineer is currently on scheduled leave',
    employee_message: 'Your ticket is being handled by Marcus Brody from Network Operations.',
    created_at: '2026-11-14T02:00:00Z',
    details: { original_engineer_id: 4, fallback_engineer_id: 3 },
  },
];

const mockPolicies = [
  {
    id: 1,
    name: 'default',
    max_workload_per_engineer: 5,
    max_reassignment_attempts: 3,
    sla_at_risk_threshold_minutes: 30,
    auto_escalate_on_no_engineer: true,
    require_skill_match: true,
    updated_at: '2026-11-14T00:00:00Z',
  },
];

describe('Phase 5.1 — Unified Frontend & Workforce Continuity Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getIncidents).mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
    vi.mocked(api.getIncident).mockResolvedValue(mockIncidentDetail);
    vi.mocked(api.getIncidentExceptions).mockResolvedValue([]);
    vi.mocked(api.getWorkforceEngineers).mockResolvedValue(mockEngineers);
    vi.mocked(api.getSupportUsers).mockResolvedValue([]);
    vi.mocked(api.getMCPStatus).mockResolvedValue({ tools: [] });
    vi.mocked(api.listAssignmentPolicies).mockResolvedValue(mockPolicies);
    vi.mocked(api.listWorkforceExceptions).mockResolvedValue(mockExceptions);
    vi.mocked(api.getAgentRuns).mockResolvedValue([]);
    vi.mocked(api.getAgentRunMetrics).mockResolvedValue({ total_runs: 5, agent_breakdown: [] });
  });

  describe('Checkpoint 5.1-A: Cross-Portal Incident Navigation', () => {
    it('navigates from ApprovalsPage to Incidents queue when incident badge is clicked', async () => {
      const onNavigate = vi.fn();
      vi.mocked(api.getApprovals).mockResolvedValueOnce([
        {
          id: 55,
          type: 'access_request',
          status: 'pending',
          requested_by: 'Alex Employee',
          details: { ticket_id: 42, reason: 'Grant VPN access' },
          created_at: '2026-11-14T01:30:00',
        },
      ]);

      render(<ApprovalsPage onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByText('INC-000042')).toBeDefined();
      });

      const badge = screen.getByText('INC-000042');
      fireEvent.click(badge);
      expect(onNavigate).toHaveBeenCalledWith('incidents', 42);
    });

    it('navigates from DashboardPage SLA Breaches to Incidents queue', async () => {
      const onNavigate = vi.fn();
      const mockAdminUser = {
        id: 1,
        email: 'admin@resolvex.ai',
        role: 'administrator' as const,
        full_name: 'Admin User',
        access_token: 'admin-token',
      };
      vi.mocked(api.getSLABreaches).mockResolvedValueOnce([
        {
          incident_id: 42,
          ticket_id: 'INC-000042',
          priority: 'high',
          priority_code: null,
          status: 'assigned',
          response_due_at: null,
          resolution_due_at: null,
          response_minutes_remaining: null,
          resolution_minutes_remaining: null,
          response_risk: null,
          resolution_risk: null,
          risk: 'at_risk',
          deadline_type: 'response',
          minutes_remaining: 15,
          escalation_eligible: false,
          escalation_reason: null,
        },
      ]);

      render(<DashboardPage currentUser={mockAdminUser} onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByText('Inspect Incident →')).toBeDefined();
      });

      fireEvent.click(screen.getByText('Inspect Incident →'));
      expect(onNavigate).toHaveBeenCalledWith('incidents', 42);
    });

    it('auto-opens incident details when initialIncidentId prop is provided to IncidentsPage', async () => {
      vi.mocked(api.getIncidents).mockResolvedValueOnce({
        items: [
          {
            id: 42,
            ticket_id: 'INC-000042',
            title: 'VPN Connection Failure',
            description: 'Remote engineer cannot connect',
            status: 'assigned',
            priority: 'high',
            category: 'network',
            assigned_team: 'Network Operations',
            assigned_to: { id: 101, name: 'Marcus Brody', email: 'marcus@resolvex.ai' },
            created_at: '2026-11-14T01:00:00',
            updated_at: '2026-11-14T01:00:00',
            asset: null,
            response_due_at: null,
            resolution_due_at: null,
            resolution_summary: null,
            sla: { risk: 'at_risk', minutes_remaining: 25, breached: false },
            employee: { id: 1, name: 'Alex Employee', email: 'alex@example.test', department: 'Sales' },
          },
        ],
        total: 1,
        limit: 25,
        offset: 0,
      });
      vi.mocked(api.getIncident).mockResolvedValueOnce(mockIncidentDetail);
      vi.mocked(api.getIncidentExceptions).mockResolvedValueOnce(mockExceptions);
      vi.mocked(api.getWorkforceEngineers).mockResolvedValueOnce(mockEngineers);
      // Provide eligible engineer IDs (Marcus) for this test
      vi.mocked(api.getEligibleEngineers).mockResolvedValueOnce({
        category: '',
        priority: '',
        eligible_engineers: [{ ...mockEngineers[0], is_eligible: true }],
      });

      render(<IncidentsPage initialIncidentId={42} />);

      await waitFor(() => {
        expect(api.getIncident).toHaveBeenCalledWith(42);
        expect(screen.getAllByText('INC-000042').length).toBeGreaterThan(0);
        expect(screen.getAllByText('VPN Connection Failure').length).toBeGreaterThan(0);
      });
    });
  });

  describe('Checkpoint 5.1-B & 5.1-C: Workforce Assignment, Concurrency, and Claim/Reject', () => {
    it('displays workforce availability status and workload metrics without sensitive reasons', async () => {
      vi.mocked(api.getIncidents).mockResolvedValueOnce({ items: [], total: 0, limit: 25, offset: 0 });
      vi.mocked(api.getIncident).mockResolvedValueOnce(mockIncidentDetail);
      vi.mocked(api.getIncidentExceptions).mockResolvedValueOnce([]);
      vi.mocked(api.getWorkforceEngineers).mockResolvedValueOnce(mockEngineers);
      // Provide eligible engineer IDs (Marcus) for this test
      vi.mocked(api.getEligibleEngineers).mockResolvedValueOnce({
        category: '',
        priority: '',
        eligible_engineers: [{ ...mockEngineers[0], is_eligible: true }],
      });

      render(<IncidentsPage initialIncidentId={42} />);

      await waitFor(() => {
        expect(screen.getByText(/Assignment & Continuity Exceptions/i)).toBeDefined();
      });

      // Check that workforce engineers dropdown renders with availability status
      const options = screen.getAllByRole('option');
      const marcusOption = options.find((opt) => opt.textContent?.includes('Marcus Brody'));
      expect(marcusOption).toBeDefined();
      expect(marcusOption?.textContent).toContain('available');
      expect(marcusOption?.textContent).toContain('2/5');

      // Confidential leave reasons must NOT be present
      expect(screen.queryByText(/medical/i)).toBeNull();
      expect(screen.queryByText(/sick/i)).toBeNull();
    });

    it('claims incident with optimistic lock version and handles HTTP 409 conflict gracefully', async () => {
      vi.mocked(api.getIncidents).mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
      vi.mocked(api.getIncident).mockResolvedValue(mockIncidentDetail);
      vi.mocked(api.getIncidentExceptions).mockResolvedValue([]);
      vi.mocked(api.getWorkforceEngineers).mockResolvedValue(mockEngineers);

      // Simulate concurrency conflict (HTTP 409)
      vi.mocked(api.claimIncident).mockRejectedValueOnce(
        new Error('Incident was modified by another user. Refreshing...')
      );

      render(<IncidentsPage initialIncidentId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Claim Incident')).toBeDefined();
      });

      fireEvent.click(screen.getByText('Claim Incident'));

      await waitFor(() => {
        expect(api.claimIncident).toHaveBeenCalledWith(42, 4);
        expect(screen.getByText(/Incident was modified by another user/i)).toBeDefined();
      });
    });

    it('requires at least 5 characters to reject an assignment and submits rejection', async () => {
      vi.mocked(api.getIncidents).mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
      vi.mocked(api.getIncident).mockResolvedValue(mockIncidentDetail);
      vi.mocked(api.getIncidentExceptions).mockResolvedValue([]);
      vi.mocked(api.getWorkforceEngineers).mockResolvedValue(mockEngineers);
      vi.mocked(api.rejectIncidentAssignment).mockResolvedValueOnce({
        incident_id: 42,
        status: 'reassigned',
      });

      render(<IncidentsPage initialIncidentId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Decline')).toBeDefined();
      });

      // Open decline modal
      fireEvent.click(screen.getByText('Decline'));
      expect(screen.getByRole('heading', { name: 'Decline Assignment' })).toBeDefined();

      const textarea = screen.getByPlaceholderText(/Currently overloaded with P1/i);
      const submitBtn = screen.getByText('Confirm Decline');

      // Try with short reason (< 5 chars) -> button is disabled
      fireEvent.change(textarea, { target: { value: 'No' } });
      expect((submitBtn as HTMLButtonElement).disabled).toBe(true);
      expect(api.rejectIncidentAssignment).not.toHaveBeenCalled();

      // Submit with valid reason (>= 5 chars)
      fireEvent.change(textarea, { target: { value: 'Assigned outside my primary area of network competence' } });
      expect((submitBtn as HTMLButtonElement).disabled).toBe(false);
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(api.rejectIncidentAssignment).toHaveBeenCalledWith(
          42,
          'Assigned outside my primary area of network competence'
        );
      });
    });
  });

  describe('Checkpoint 5.1-D: Incident Continuity History in Drawer', () => {
    it('displays continuity exceptions with safe messages and formatted details', async () => {
      vi.mocked(api.getIncidents).mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
      vi.mocked(api.getIncident).mockResolvedValue(mockIncidentDetail);
      vi.mocked(api.getIncidentExceptions).mockResolvedValue(mockExceptions);
      vi.mocked(api.getWorkforceEngineers).mockResolvedValue(mockEngineers);

      render(<IncidentsPage initialIncidentId={42} />);

      expect(await screen.findByText('engineer on leave')).toBeInTheDocument();
      expect(screen.getByText('warning')).toBeInTheDocument();
      expect(screen.getAllByText(/Elena Rostova/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Marcus Brody/).length).toBeGreaterThan(0);
      expect(screen.getByText(/Your ticket is being handled by Marcus Brody from Network Operations/)).toBeInTheDocument();
    });
  });

  describe('Checkpoint 5.1-E & 5.1-F: CommandCenter Policies and Global Exception Stream', () => {
    it('renders continuity policy metrics and allows administrator to edit policies', async () => {
      vi.mocked(api.listAssignmentPolicies).mockResolvedValue(mockPolicies);
      vi.mocked(api.listWorkforceExceptions).mockResolvedValue(mockExceptions);
      vi.mocked(api.getWorkforceEngineers).mockResolvedValue(mockEngineers);
      vi.mocked(api.updateAssignmentPolicy).mockResolvedValue({ status: 'updated' });

      const adminUser = {
        id: 1,
        email: 'admin@resolvex.ai',
        role: 'administrator' as const,
        full_name: 'Admin User',
        access_token: 'admin-token',
      };

      // Mock window.confirm
      vi.spyOn(window, 'confirm').mockImplementation(() => true);

      render(<CommandCenterPage currentUser={adminUser} />);

      await waitFor(() => {
        expect(screen.getByText('Intelligent Assignment & Continuity Policies')).toBeDefined();
        expect(screen.getByText('Configure Policy')).toBeDefined();
      });

      // Open policy modal
      fireEvent.click(screen.getByText('Configure Policy'));
      expect(screen.getByText(/Configure Continuity Policy: default/i)).toBeDefined();

      // Submit change
      fireEvent.click(screen.getByText('Save Policy Changes'));

      await waitFor(() => {
        expect(api.updateAssignmentPolicy).toHaveBeenCalledWith('default', expect.objectContaining({
          max_workload_per_engineer: 5,
          max_reassignment_attempts: 3,
          sla_at_risk_threshold_minutes: 30,
        }));
      });
    });

    it('restricts policy editing for non-administrators with Admin Governed badge', async () => {
      vi.mocked(api.listAssignmentPolicies).mockResolvedValue(mockPolicies);
      vi.mocked(api.listWorkforceExceptions).mockResolvedValue([]);
      vi.mocked(api.getWorkforceEngineers).mockResolvedValue([]);

      const supportUser = {
        id: 2,
        email: 'support@resolvex.ai',
        role: 'support_engineer' as const,
        full_name: 'Support Engineer',
        access_token: 'support-token',
      };

      render(<CommandCenterPage currentUser={supportUser} />);

      await waitFor(() => {
        expect(screen.getByText('Admin Governed')).toBeDefined();
        expect(screen.queryByText('Configure Policy')).toBeNull();
      });
    });

    it('renders global exception stream with search, filter, and clickable incident link', async () => {
      const onNavigate = vi.fn();
      vi.mocked(api.listAssignmentPolicies).mockResolvedValue(mockPolicies);
      vi.mocked(api.listWorkforceExceptions).mockResolvedValue(mockExceptions);
      vi.mocked(api.getWorkforceEngineers).mockResolvedValue(mockEngineers);

      render(<CommandCenterPage onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByText('Global Workforce Continuity Exception Stream')).toBeDefined();
        expect(screen.getByText('INC-000042')).toBeDefined();
      });

      // Click on INC-000042 in global exception feed
      const incBtn = screen.getByText('INC-000042');
      fireEvent.click(incBtn);
      expect(onNavigate).toHaveBeenCalledWith('incidents', 42);
    });
  });
});
