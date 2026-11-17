import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { IncidentsPage } from '../pages/IncidentsPage';
import {
  getIncident,
  getIncidents,
  getMCPStatus,
  getSupportUsers,
  investigateIncident,
  updateIncident,
} from '../services/api';

vi.mock('../services/api', () => ({
  addIncidentComment: vi.fn(),
  executeMcpTool: vi.fn(),
  getIncident: vi.fn(),
  getIncidentExceptions: vi.fn().mockResolvedValue([]),
  getIncidents: vi.fn(),
  getMCPStatus: vi.fn(),
  getSupportUsers: vi.fn(),
  getWorkforceEngineers: vi.fn().mockResolvedValue([]),
  getEligibleEngineers: vi.fn().mockResolvedValue([]),
  investigateIncident: vi.fn(),
  updateIncident: vi.fn(),
}));

const incident = {
  id: 12,
  ticket_id: 'INC-000012',
  title: 'Portal unavailable',
  description: 'The company portal is unavailable on the corporate network.',
  status: 'in_progress',
  priority: 'high',
  category: 'network',
  assigned_team: 'Network Operations',
  assigned_to: { id: 2, name: 'Support One', email: 'support@example.test' },
  asset: null,
  created_at: '2026-11-14T01:00:00',
  updated_at: '2026-11-14T01:00:00',
  first_response_at: null,
  resolved_at: null,
  response_due_at: null,
  resolution_due_at: null,
  resolution_summary: null,
  sla: { risk: 'unknown', minutes_remaining: null, breached: false },
  employee: {
    id: 1,
    name: 'Alex Employee',
    email: 'employee@example.test',
    department: 'Finance',
    assets: [],
  },
  history: [],
  comments: [],
  related_incidents: [],
  agent_runs: [],
  mcp_calls: [],
};

describe('IncidentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getIncidents).mockResolvedValue({
      items: [incident],
      total: 1,
      limit: 25,
      offset: 0,
    });
    vi.mocked(getIncident).mockResolvedValue(incident);
    vi.mocked(getSupportUsers).mockResolvedValue([
      { id: 2, name: 'Support One', email: 'support@example.test' },
    ]);
    vi.mocked(getMCPStatus).mockResolvedValue({
      tools: [{ name: 'check_network_status' }],
    });
  });

  it('loads the queue and opens the selected incident investigation details', async () => {
    render(<IncidentsPage />);

    expect(await screen.findByText('Portal unavailable')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /INC-000012/ }));
    expect(await screen.findByText('Alex Employee')).toBeInTheDocument();
    expect(screen.queryByText('Reporter assets')).not.toBeInTheDocument();
    expect(getIncident).toHaveBeenCalledWith(12);
  });

  it('does not resolve without verification and saves confirmed resolution notes', async () => {
    render(<IncidentsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /INC-000012/ }));

    fireEvent.change(await screen.findByLabelText('Status'), { target: { value: 'resolved' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Resolution requires notes');
    expect(updateIncident).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Resolution notes'), {
      target: { value: 'Confirmed portal access restored.' },
    });
    fireEvent.click(screen.getByLabelText('I verified the resolution outcome.'));
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => {
      expect(updateIncident).toHaveBeenCalledWith(12, expect.objectContaining({
        status: 'resolved',
        resolution_summary: 'Confirmed portal access restored.',
        resolution_verified: true,
      }));
    });
  });

  it('shows investigation evidence and labels simulated diagnostics', async () => {
    vi.mocked(investigateIncident).mockResolvedValue({
      incident_id: 12,
      employee_id: 1,
      user_message: incident.description,
      intent: 'incident',
      category: 'network',
      priority: 'high',
      retrieved_chunks: [{ doc: 'Network Runbook', chunk: 'Check DNS resolution.', score: 0.91 }],
      diagnostics: [{ tool: 'check_network_status', result: { status: 'degraded' }, simulated: true }],
      proposed_resolution: 'Verify DNS and gateway reachability.',
      requires_approval: false,
      ticket_status: 'in_progress',
      agent_trace: [{ agent: 'Diagnostic Agent', summary: 'Network check completed.', status: 'completed', started_at: '', duration_ms: 4 }],
      errors: [],
      is_demo: true,
    });
    render(<IncidentsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /INC-000012/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Investigate/ }));

    expect(await screen.findByText(/DEMO MODE: simulated AI workflow/)).toBeInTheDocument();
    expect(screen.getByText('Network Runbook')).toBeInTheDocument();
    expect(screen.getByText('Simulated')).toBeInTheDocument();
  });
});
