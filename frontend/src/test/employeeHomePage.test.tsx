import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { EmployeeHomePage } from '../pages/EmployeeHomePage';
import {
  createEmployeeServiceRequest,
  EmployeePortalData,
  getEmployeeDashboard,
  getEmployeeTicket,
  getEmployeeTickets,
  markEmployeeNotificationRead,
  submitEmployeeResolutionFeedback,
  updateEmployeeProfile,
  User,
} from '../services/api';

vi.mock('../services/api', () => ({
  addEmployeeTicketComment: vi.fn(),
  createEmployeeServiceRequest: vi.fn(),
  getEmployeeDashboard: vi.fn(),
  getEmployeeTicket: vi.fn(),
  getEmployeeTickets: vi.fn(),
  submitEmployeeResolutionFeedback: vi.fn(),
  markEmployeeNotificationRead: vi.fn(),
  reopenEmployeeTicket: vi.fn(),
  updateEmployeeProfile: vi.fn(),
}));

const employee: User = {
  id: 8,
  email: 'employee@example.test',
  role: 'employee',
  access_token: 'employee-token',
};

const portalData: EmployeePortalData = {
  profile: {
    id: 8,
    email: employee.email,
    role: 'employee',
    full_name: 'Alex Employee',
    department: 'Engineering',
    phone: '+1 555-0199',
  },
  metrics: {
    total_tickets: 2,
    open_tickets: 1,
    in_progress_tickets: 1,
    resolved_tickets: 0,
    pending_service_requests: 1,
    pending_approvals: 1,
  },
  recent_tickets: [],
  recent_activity: [
    {
      id: 101,
      title: 'SR-000012 submitted',
      message: 'Your request for Python installation was received.',
      notification_type: 'service_request',
      created_at: '2026-11-14T02:00:00',
      read: false,
    },
  ],
  announcements: [
    {
      id: 1,
      title: 'Scheduled Network Maintenance',
      message: 'Core routers will reboot at midnight UTC.',
      published_at: '2026-11-14T00:00:00',
    },
  ],
  frequently_used_services: [
    { category: 'software_installation', request_count: 3 },
  ],
  service_catalog: [
    { id: 'software_installation', name: 'Software Installation' },
    { id: 'vpn_access', name: 'VPN Access' },
  ],
  recommendations: ['You have 1 open ticket(s). Check status before creating a new ticket.'],
  pending_approvals: [],
  approvals: [
    {
      id: 5,
      request_type: 'software_installation',
      requested_action: 'Install Python development libraries',
      status: 'pending',
      created_at: '2026-11-14T01:00:00',
      decided_at: null,
      decision_reason: null,
      ticket_id: 'SR-000012',
    },
  ],
  assigned_assets: [
    {
      id: 42,
      type: 'Laptop',
      model: 'MacBook Pro 16"',
      serial_number: 'MBP-2026-8891',
      assigned_at: '2026-01-15T09:00:00',
    },
  ],
};

describe('EmployeeHomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getEmployeeDashboard).mockResolvedValue(portalData);
    vi.mocked(getEmployeeTickets).mockResolvedValue([]);
    vi.mocked(createEmployeeServiceRequest).mockResolvedValue({
      ticket_id: 'SR-000012',
      record_id: 12,
      ticket_type: 'service_request',
      category: 'software_installation',
      priority: 'medium',
      description: 'Please install the approved development tools.',
      status: 'pending_approval',
      assigned_team: null,
      created_at: '2026-11-14T01:00:00',
      updated_at: '2026-11-14T01:00:00',
      response_due_at: null,
      resolution_due_at: null,
      resolution_summary: null,
      sla_status: null,
      approval_id: 5,
      requires_approval: true,
    });
  });

  it('renders database-backed metrics and submits a catalog request', async () => {
    render(<EmployeeHomePage currentUser={employee} onNavigate={vi.fn()} />);

    expect(await screen.findByText('Welcome, Alex Employee')).toBeInTheDocument();
    expect(screen.getByText('Total tickets')).toBeInTheDocument();
    expect(screen.getByText('Pending requests')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Request details'), {
      target: { value: 'Please install the approved development tools.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Submit request' }));

    await waitFor(() => {
      expect(createEmployeeServiceRequest).toHaveBeenCalledWith(
        'software_installation',
        'Please install the approved development tools.',
      );
    });
    expect(await screen.findByRole('status')).toHaveTextContent(
      'SR-000012 was submitted. Approval #5 is pending.',
    );
  });

  it('records ticket resolution feedback and confirms the saved result', async () => {
    vi.mocked(getEmployeeTickets).mockResolvedValue([
      {
        ticket_id: 'INC-000014',
        record_id: 14,
        ticket_type: 'incident',
        category: 'network',
        priority: 'medium',
        description: 'The company portal is not opening.',
        status: 'in_progress',
        assigned_team: 'Network Operations',
        created_at: '2026-11-14T01:00:00',
        updated_at: '2026-11-14T01:00:00',
        response_due_at: null,
        resolution_due_at: null,
        resolution_summary: null,
        sla_status: null,
      },
    ]);
    vi.mocked(getEmployeeTicket).mockResolvedValue({
      ticket_id: 'INC-000014',
      record_id: 14,
      ticket_type: 'incident',
      category: 'network',
      priority: 'medium',
      description: 'The company portal is not opening.',
      status: 'in_progress',
      assigned_team: 'Network Operations',
      created_at: '2026-11-14T01:00:00',
      updated_at: '2026-11-14T01:00:00',
      response_due_at: null,
      resolution_due_at: null,
      resolution_summary: null,
      sla_status: null,
      conversation_history: [],
    });
    vi.mocked(submitEmployeeResolutionFeedback).mockResolvedValue({
      ticket_id: 'INC-000014',
      status: 'in_progress',
      feedback_recorded: true,
    });

    render(<EmployeeHomePage currentUser={employee} onNavigate={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'INC-000014' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Not resolved' }));

    await waitFor(() => {
      expect(submitEmployeeResolutionFeedback).toHaveBeenCalledWith('INC-000014', false);
    });
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Support was notified that this request is not resolved.',
    );
  });

  it('updates permitted profile fields on form submission', async () => {
    vi.mocked(updateEmployeeProfile).mockResolvedValue({
      id: 8,
      email: employee.email,
      role: 'employee',
      full_name: 'Alex E. Senior',
      department: 'Engineering',
      phone: '+1 555-9999',
    });

    render(<EmployeeHomePage currentUser={employee} onNavigate={vi.fn()} />);
    await screen.findByText('Welcome, Alex Employee');

    fireEvent.change(screen.getByLabelText('Display name'), {
      target: { value: 'Alex E. Senior' },
    });
    fireEvent.change(screen.getByLabelText('Contact phone'), {
      target: { value: '+1 555-9999' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save permitted fields' }));

    await waitFor(() => {
      expect(updateEmployeeProfile).toHaveBeenCalledWith({
        full_name: 'Alex E. Senior',
        phone: '+1 555-9999',
      });
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Profile updated successfully.');
  });

  it('marks unread activity notifications as read', async () => {
    vi.mocked(markEmployeeNotificationRead).mockResolvedValue();

    render(<EmployeeHomePage currentUser={employee} onNavigate={vi.fn()} />);
    await screen.findByText('Recent Activity');

    const markReadBtn = await screen.findByRole('button', { name: 'Mark read' });
    fireEvent.click(markReadBtn);

    await waitFor(() => {
      expect(markEmployeeNotificationRead).toHaveBeenCalledWith(101);
    });
  });

  it('renders assigned assets, recommendations, and announcements', async () => {
    render(<EmployeeHomePage currentUser={employee} onNavigate={vi.fn()} />);

    expect((await screen.findAllByText('MacBook Pro 16"')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('MBP-2026-8891').length).toBeGreaterThan(0);
    expect(
      screen.getByText('You have 1 open ticket(s). Check status before creating a new ticket.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Scheduled Network Maintenance')).toBeInTheDocument();
    expect(screen.getByText('Core routers will reboot at midnight UTC.')).toBeInTheDocument();
  });
});