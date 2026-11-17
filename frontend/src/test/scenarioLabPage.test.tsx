import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ScenarioLabPage } from '../pages/ScenarioLabPage';

const api = vi.hoisted(() => ({
  listLabScenarios: vi.fn(),
  runLabScenario: vi.fn(),
  runAllLabScenarios: vi.fn(),
  exportLabReport: vi.fn(),
}));

vi.mock('../services/api', () => api);

const mockScenarios = [
  {
    id: 'scenario_1',
    name: 'Normal VPN connectivity issue',
    category: 'Network & VPN',
    description: 'Primary eligible engineer is active and available; ticket is assigned directly.',
    expected_outcome: 'Incident assigned directly to primary engineer with SLA preserved.',
  },
  {
    id: 'scenario_2',
    name: 'Vague employee complaint',
    category: 'Triage & NLP',
    description: 'Ambiguous description defaults safely to general queue.',
    expected_outcome: 'Triage assigns general fallback category with response SLA.',
  },
  {
    id: 'scenario_4',
    name: 'Engineer unavailable due to leave',
    category: 'Workforce & Leave',
    description: 'Alex Rivera on leave; reassigns to Sarah Chen.',
    expected_outcome: 'Exception detected; reassigned without leaking leave details.',
  },
];

const mockResult = {
  scenario_id: 'scenario_1',
  run_id: 'LAB-RUN-1794719000-scenario_1',
  name: 'Normal VPN connectivity issue',
  category: 'Network & VPN',
  description: 'Primary eligible engineer is active and available.',
  execution_status: 'completed',
  verdict: 'PASS' as const,
  passed_checks: ['Direct assignment completed', 'SLA initialized', 'Primary engineer assigned'],
  failed_checks: [],
  warnings: [],
  input_conditions: { category: 'vpn', priority: 'high', simulated: true },
  expected_outcome: 'Incident assigned directly to primary engineer with SLA preserved.',
  actual_outcome: 'Directly assigned to Sarah Chen. SLA preserved=True.',
  agent_sequence: ['Triage Agent', 'Supervisor Agent', 'Diagnostic Agent', 'Resolution Agent', 'Ticket Agent'],
  mcp_calls: [{ tool: 'check_network_connectivity', status: 'success', simulated: true }],
  assignment_decision: { id: 4, name: 'Sarah Chen' },
  notifications_generated: ['Ticket INC-000001 assigned'],
  audit_events: ['incident.assigned: user_id=4'],
  execution_steps: [
    '1. Evaluating primary engineer availability for Sarah Chen (available).',
    '2. Direct assignment executed: assigned_to=Sarah Chen.',
  ],
  execution_duration_ms: 120,
  simulated: true,
  executed_at: '2026-11-15T09:00:00Z',
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('ScenarioLabPage', () => {
  it('renders the lab header, strict test isolation banner, and scenario cards', async () => {
    api.listLabScenarios.mockResolvedValue(mockScenarios);

    render(<ScenarioLabPage />);

    expect(await screen.findByText('Scenario Testing Lab')).toBeInTheDocument();
    expect(screen.getByText(/Strict Test Isolation Active/i)).toBeInTheDocument();
    expect(screen.getByText('Normal VPN connectivity issue')).toBeInTheDocument();
    expect(screen.getByText('Vague employee complaint')).toBeInTheDocument();
    expect(screen.getByText('Engineer unavailable due to leave')).toBeInTheDocument();
  });

  it('filters scenarios by search query and category buttons', async () => {
    api.listLabScenarios.mockResolvedValue(mockScenarios);

    render(<ScenarioLabPage />);
    await screen.findByText('Normal VPN connectivity issue');

    // Filter by search
    const searchInput = screen.getByPlaceholderText(/Search 20 scenarios/i);
    fireEvent.change(searchInput, { target: { value: 'leave' } });

    expect(screen.getByText('Engineer unavailable due to leave')).toBeInTheDocument();
    expect(screen.queryByText('Normal VPN connectivity issue')).not.toBeInTheDocument();

    // Reset search and filter by category
    fireEvent.change(searchInput, { target: { value: '' } });
    const nlpBtn = screen.getByRole('button', { name: 'Triage & NLP' });
    fireEvent.click(nlpBtn);

    expect(screen.getByText('Vague employee complaint')).toBeInTheDocument();
    expect(screen.queryByText('Engineer unavailable due to leave')).not.toBeInTheDocument();
  });

  it('runs an individual scenario and displays execution steps, passed checks, and verdict', async () => {
    api.listLabScenarios.mockResolvedValue(mockScenarios);
    api.runLabScenario.mockResolvedValue(mockResult);

    render(<ScenarioLabPage />);
    await screen.findByText('Normal VPN connectivity issue');

    const runButtons = screen.getAllByRole('button', { name: /^Run$/i });
    fireEvent.click(runButtons[0]);

    await waitFor(() => {
      expect(api.runLabScenario).toHaveBeenCalledWith('scenario_1');
    });

    // Inspector checks
    expect(await screen.findByText('Directly assigned to Sarah Chen. SLA preserved=True.')).toBeInTheDocument();
    expect(screen.getByText('Direct assignment completed')).toBeInTheDocument();
    expect(screen.getByText('SLA initialized')).toBeInTheDocument();
    expect(screen.getByText('check_network_connectivity')).toBeInTheDocument();
    expect(screen.getAllByText('PASS').length).toBeGreaterThan(0);
  });

  it('runs all scenarios in batch and displays the summary metrics', async () => {
    api.listLabScenarios.mockResolvedValue(mockScenarios);
    api.runAllLabScenarios.mockResolvedValue({
      batch_id: 'BATCH-12345',
      total_scenarios: 20,
      passed_count: 20,
      failed_count: 0,
      warning_count: 2,
      pass_rate_pct: 100,
      total_duration_ms: 1850,
      results: [mockResult],
      simulated: true,
      executed_at: '2026-11-15T09:00:00Z',
    });

    render(<ScenarioLabPage />);
    await screen.findByText('Normal VPN connectivity issue');

    const runAllBtn = screen.getByRole('button', { name: /Run All 20 Scenarios/i });
    fireEvent.click(runAllBtn);

    await waitFor(() => {
      expect(api.runAllLabScenarios).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText('100%')).toBeInTheDocument();
    expect(screen.getByText('1850 ms')).toBeInTheDocument();
  });
});
