import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { EmployeeChatPage } from '../pages/EmployeeChatPage';
import { runAgentChat, submitEmployeeResolutionFeedback, User } from '../services/api';

vi.mock('../services/api', () => ({
  runAgentChat: vi.fn(),
  submitEmployeeResolutionFeedback: vi.fn(),
}));

const employee: User = {
  id: 8,
  email: 'employee@example.test',
  role: 'employee',
  access_token: 'employee-token',
};

describe('EmployeeChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('resumes the employee thread and persists its returned thread ID', async () => {
    sessionStorage.setItem('resolvex-agent-thread-8', 'employee_8_existing');
    vi.mocked(runAgentChat).mockResolvedValue({
      incident_id: 14,
      employee_id: employee.id,
      user_message: 'The issue is still happening.',
      intent: 'incident',
      category: 'network',
      priority: 'medium',
      retrieved_chunks: [],
      diagnostics: [],
      proposed_resolution: 'The support team will continue investigating.',
      requires_approval: false,
      ticket_status: 'in_progress',
      agent_trace: [],
      errors: [],
      is_demo: true,
      thread_id: 'employee_8_existing',
    });

    render(<EmployeeChatPage currentUser={employee} />);
    fireEvent.change(screen.getByPlaceholderText(/Describe your IT issue/), {
      target: { value: 'The issue is still happening.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(runAgentChat).toHaveBeenCalledWith(
        'The issue is still happening.',
        'employee_8_existing',
      );
    });
    expect(await screen.findByText('The support team will continue investigating.')).toBeInTheDocument();
    await waitFor(() => {
      expect(sessionStorage.getItem('resolvex-agent-thread-8')).toBe('employee_8_existing');
    });
  });

  it('renders assistant welcome message and clicking a scenario sends its prompt', async () => {
    vi.mocked(runAgentChat).mockResolvedValue({
      incident_id: 101,
      employee_id: employee.id,
      user_message: 'My laptop is connected to Wi-Fi, but the company portal is not opening.',
      intent: 'incident',
      category: 'network',
      priority: 'medium',
      retrieved_chunks: [
        {
          doc: 'Network Connectivity Guide.md',
          chunk: 'Verify local gateway and DNS resolution for portal.resolvex.ai',
          score: 0.94,
        },
      ],
      diagnostics: [
        {
          tool: 'check_network_status',
          result: { status: 'degraded', latency_ms: 120 },
          simulated: true,
        },
      ],
      proposed_resolution: 'Flush DNS cache and re-authenticate via captive portal.',
      requires_approval: false,
      ticket_status: 'in_progress',
      agent_trace: [
        {
          agent: 'Triage',
          summary: 'Classified incident as network with medium priority',
          started_at: '2026-11-14T01:00:00',
          duration_ms: 45,
          status: 'completed',
        },
      ],
      errors: [],
      is_demo: true,
      thread_id: 'thread-portal-101',
    });

    render(<EmployeeChatPage currentUser={employee} onNavigate={vi.fn()} />);

    // Welcome title & scenario shortcuts
    expect(screen.getByText('How can ResolveX AI help you today?')).toBeInTheDocument();
    const portalScenarioBtn = screen.getAllByText('Portal Connectivity')[0];
    fireEvent.click(portalScenarioBtn);

    await waitFor(() => {
      expect(runAgentChat).toHaveBeenCalledWith(
        'My laptop is connected to Wi-Fi, but the company portal is not opening.',
        undefined,
      );
    });

    // Verify rich telemetry response elements
    expect(await screen.findByText('INC-000101')).toBeInTheDocument();
    expect(screen.getByText('Flush DNS cache and re-authenticate via captive portal.')).toBeInTheDocument();
    expect(screen.getByText('Network Connectivity Guide.md')).toBeInTheDocument();
    expect(screen.getByText('Tool: check_network_status')).toBeInTheDocument();
    expect(screen.getByText('Simulated')).toBeInTheDocument();
    expect(screen.getByText('DEMO MODE: simulated')).toBeInTheDocument();
  });

  it('records resolution feedback in AI chat conversation', async () => {
    vi.mocked(runAgentChat).mockResolvedValue({
      incident_id: 102,
      employee_id: employee.id,
      user_message: 'VPN issue',
      intent: 'incident',
      category: 'vpn',
      priority: 'medium',
      retrieved_chunks: [],
      diagnostics: [],
      proposed_resolution: 'Restart the VPN service and reconnect.',
      requires_approval: false,
      ticket_status: 'open',
      agent_trace: [],
      errors: [],
      is_demo: false,
      thread_id: 'thread-vpn-102',
    });
    vi.mocked(submitEmployeeResolutionFeedback).mockResolvedValue({
      ticket_id: 'INC-000102',
      status: 'resolved',
      feedback_recorded: true,
    });

    render(<EmployeeChatPage currentUser={employee} onNavigate={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(/Describe your IT issue/), {
      target: { value: 'VPN issue' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Restart the VPN service and reconnect.')).toBeInTheDocument();

    const resolvedBtn = screen.getByRole('button', { name: 'Resolved' });
    fireEvent.click(resolvedBtn);

    await waitFor(() => {
      expect(submitEmployeeResolutionFeedback).toHaveBeenCalledWith('INC-000102', true);
    });
    expect(await screen.findByText('Resolution feedback recorded')).toBeInTheDocument();
  });

  it('resets conversation on New Conversation button click', async () => {
    sessionStorage.setItem('resolvex-agent-thread-8', 'existing-thread');
    vi.mocked(runAgentChat).mockResolvedValue({
      incident_id: 103,
      employee_id: employee.id,
      user_message: 'Initial issue',
      intent: 'incident',
      category: 'general',
      priority: 'low',
      retrieved_chunks: [],
      diagnostics: [],
      proposed_resolution: 'General guidance provided.',
      requires_approval: false,
      ticket_status: 'open',
      agent_trace: [],
      errors: [],
      is_demo: true,
      thread_id: 'existing-thread',
    });

    render(<EmployeeChatPage currentUser={employee} />);
    fireEvent.change(screen.getByPlaceholderText(/Describe your IT issue/), {
      target: { value: 'Initial issue' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('General guidance provided.')).toBeInTheDocument();

    const resetBtn = screen.getByRole('button', { name: 'New Conversation' });
    fireEvent.click(resetBtn);

    expect(screen.getByText('How can ResolveX AI help you today?')).toBeInTheDocument();
    expect(sessionStorage.getItem('resolvex-agent-thread-8')).toBeNull();
  });
});