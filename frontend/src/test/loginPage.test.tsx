import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { LoginPage } from '../pages/LoginPage';
import { login } from '../services/api';

vi.mock('../services/api', () => ({
  login: vi.fn(),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('removes the portfolio badge and allows the password to be shown and hidden', () => {
    render(<LoginPage onLoginSuccess={vi.fn()} />);

    expect(screen.queryByText('HCLTech USM & Generative AI Portfolio Demo')).not.toBeInTheDocument();

    const password = screen.getByLabelText('Password');
    expect(password).toHaveAttribute('type', 'password');

    fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(password).toHaveAttribute('type', 'password');
    expect(login).not.toHaveBeenCalled();
  });

  it('renders product identity, all three roles, and platform capabilities', () => {
    render(<LoginPage onLoginSuccess={vi.fn()} />);

    // Product identity
    expect(screen.getByRole('heading', { level: 1, name: 'ResolveX AI' })).toBeInTheDocument();
    expect(
      screen.getByText('Autonomous Unified Service Management (USM) Platform'),
    ).toBeInTheDocument();

    // All three roles
    expect(screen.getByText('Employee')).toBeInTheDocument();
    expect(
      screen.getByText('Report IT issues via AI Chat, view tickets and track SLA.'),
    ).toBeInTheDocument();

    expect(screen.getByText('Support Engineer')).toBeInTheDocument();
    expect(
      screen.getByText('Review triage, execute diagnostics and approve pending actions.'),
    ).toBeInTheDocument();

    expect(screen.getByText('Administrator')).toBeInTheDocument();
    expect(
      screen.getByText('Manage CMDB assets, knowledge runbooks, MCP tools and policies.'),
    ).toBeInTheDocument();

    // Capabilities
    expect(screen.getByText('Intelligent Incident Management')).toBeInTheDocument();
    expect(screen.getByText('AI-Assisted Troubleshooting')).toBeInTheDocument();
    expect(screen.getByText('Multi-Agent Orchestration')).toBeInTheDocument();
    expect(screen.getByText('MCP-Powered Diagnostics')).toBeInTheDocument();
    expect(screen.getByText('Knowledge-Base-Assisted Resolution')).toBeInTheDocument();
    expect(screen.getByText('SLA Monitoring & Service Governance')).toBeInTheDocument();
  });

  it('does not expose internal port numbers or permanently visible default passwords', () => {
    render(<LoginPage onLoginSuccess={vi.fn()} />);

    // Must not display internal port infrastructure details
    expect(screen.queryByText(/Port 8080/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Port 8001/i)).not.toBeInTheDocument();

    // Must not display permanently visible default password text
    expect(screen.queryByText(/Default: Demo123/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Fill Demo Password \(Demo123\)/i)).not.toBeInTheDocument();
  });

  it('switches roles and populates corresponding default email addresses', () => {
    render(<LoginPage onLoginSuccess={vi.fn()} />);

    const emailInput = screen.getByLabelText('Email');
    expect(emailInput).toHaveValue('employee@resolvex.ai');

    // Switch to Support Engineer
    const supportRadio = screen.getByRole('radio', { name: /Support Engineer/i });
    fireEvent.click(supportRadio);
    expect(supportRadio).toHaveAttribute('aria-checked', 'true');
    expect(emailInput).toHaveValue('support@resolvex.ai');
    expect(screen.getByRole('button', { name: /Sign in as Support Engineer/i })).toBeInTheDocument();

    // Switch to Administrator
    const adminRadio = screen.getByRole('radio', { name: /Administrator/i });
    fireEvent.click(adminRadio);
    expect(adminRadio).toHaveAttribute('aria-checked', 'true');
    expect(emailInput).toHaveValue('admin@resolvex.ai');
    expect(screen.getByRole('button', { name: /Sign in as Administrator/i })).toBeInTheDocument();
  });

  it('displays session-expiry or notice feedback when notice prop is provided', () => {
    render(
      <LoginPage
        onLoginSuccess={vi.fn()}
        notice="Your session expired or was revoked. Please sign in again."
      />,
    );

    const statusBanner = screen.getByRole('status');
    expect(statusBanner).toHaveTextContent(
      'Your session expired or was revoked. Please sign in again.',
    );
  });

  it('validates required fields and email format with inline feedback', async () => {
    render(<LoginPage onLoginSuccess={vi.fn()} />);

    const emailInput = screen.getByLabelText('Email');
    const submitBtn = screen.getByRole('button', { name: /Sign in as Employee/i });

    // Clear email and submit
    fireEvent.change(emailInput, { target: { value: '' } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText('Email address is required.')).toBeInTheDocument();
    expect(screen.getByText('Password is required.')).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();

    // Invalid email format
    fireEvent.change(emailInput, { target: { value: 'not-an-email' } });
    fireEvent.click(submitBtn);

    expect(
      await screen.findByText('Please enter a valid work email address.'),
    ).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('provides clearly labelled optional demo access with sandbox disclaimers', () => {
    render(<LoginPage onLoginSuccess={vi.fn()} />);

    const passwordInput = screen.getByLabelText('Password');
    expect(passwordInput).toHaveValue('');

    // Initially demo fill button is not visible
    expect(screen.queryByRole('button', { name: 'Fill Demo Password' })).not.toBeInTheDocument();

    // Click optional demo environment access interaction
    const demoToggle = screen.getByRole('button', { name: /Demo Environment Access/i });
    fireEvent.click(demoToggle);

    // Verify demonstration only disclaimer
    expect(screen.getByText('Demonstration Only')).toBeInTheDocument();
    expect(
      screen.getByText(/Pre-configured evaluation accounts operate with simulated data/i),
    ).toBeInTheDocument();

    // Click fill demo password button
    fireEvent.click(screen.getByRole('button', { name: 'Fill Demo Password' }));
    expect(passwordInput).toHaveValue('Demo123');
  });

  it('handles successful authentication and invokes onLoginSuccess', async () => {
    const mockUser = {
      id: 1,
      email: 'employee@resolvex.ai',
      role: 'employee' as const,
      access_token: 'fake-jwt-token',
    };
    vi.mocked(login).mockResolvedValueOnce(mockUser);

    const onLoginSuccess = vi.fn();
    render(<LoginPage onLoginSuccess={onLoginSuccess} />);

    // Open demo access and fill password
    fireEvent.click(screen.getByRole('button', { name: /Demo Environment Access/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Fill Demo Password' }));

    const submitBtn = screen.getByRole('button', { name: /Sign in as Employee/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith('employee', 'employee@resolvex.ai', 'Demo123');
      expect(onLoginSuccess).toHaveBeenCalledWith(mockUser);
    });
  });

  it('displays user-friendly error message on authentication failure', async () => {
    vi.mocked(login).mockRejectedValueOnce(new Error('Invalid email, password, or role'));

    render(<LoginPage onLoginSuccess={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /Demo Environment Access/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Fill Demo Password' }));
    fireEvent.click(screen.getByRole('button', { name: /Sign in as Employee/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(
      'Invalid credentials or role mismatch. Ensure your email and password correspond to the selected role.',
    );
  });
});