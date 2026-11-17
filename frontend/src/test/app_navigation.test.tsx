// App‑level URL navigation tests for Phase 5.1‑A
// ---------------------------------------------------
// These tests render the real <App/> component, perform a login via the mocked
// `login` service, and verify that the browser URL and internal state stay in
// sync. All API functions are mocked exactly once, avoiding duplicate keys.

import { render, screen, waitFor, act, cleanup } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../services/api';
import { App } from '../App';

// ---------------------------------------------------------------------------
// Mock the entire api module – each export appears exactly once.
// ---------------------------------------------------------------------------
vi.mock('../services/api', () => ({
  // Authentication
  login: vi.fn().mockResolvedValue({
    id: 1,
    email: 'admin@resolvex.ai',
    role: 'administrator' as const,
    access_token: 'admin-token',
  }),
  logout: vi.fn(),
  setAccessToken: vi.fn(),

  // Core data for IncidentsPage navigation
  getIncidents: vi.fn().mockResolvedValue({
    items: [
      { id: 42, ticket_id: 'INC-000042', title: 'Issue 42' },
      { id: 43, ticket_id: 'INC-000043', title: 'Issue 43' },
    ],
    total: 2,
    limit: 25,
    offset: 0,
  }),
  getIncident: vi.fn().mockImplementation((id: number) =>
    Promise.resolve({
      id,
      ticket_id: `INC-0000${id}`,
      title: `Issue ${id}`,
    })
  ),
  getWorkforceEngineers: vi.fn().mockResolvedValue([]),
  getEligibleEngineers: vi.fn().mockResolvedValue({ eligible_engineers: [] }),
  getIncidentExceptions: vi.fn().mockResolvedValue([]),

  // Stubs for pages that may be rendered after navigation
  getDashboardStats: vi.fn().mockResolvedValue({}),
  getSLABreaches: vi.fn().mockResolvedValue([]),
  listAssignmentPolicies: vi.fn().mockResolvedValue([]),
  listWorkforceExceptions: vi.fn().mockResolvedValue([]),
  getSupportUsers: vi.fn().mockResolvedValue([]),
  getMCPStatus: vi.fn().mockResolvedValue({ tools: [] }),

  // No‑op stubs for other service functions used elsewhere
  addIncidentComment: vi.fn(),
  claimIncident: vi.fn(),
  executeMcpTool: vi.fn(),
  getAgentRuns: vi.fn(),
  getAgentRunMetrics: vi.fn(),
  getApprovals: vi.fn(),
  getOperationalInsights: vi.fn(),
  getSLAPolicies: vi.fn(),
  getSLATrendPoint: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Helper: perform a full login flow (select role, fill demo password, submit)
// ---------------------------------------------------------------------------
async function loginAsAdmin() {
  const existingRadio = screen.queryByRole('radio', { name: /administrator/i });
  if (!existingRadio) {
    cleanup();
    render(<App />);
  }
  // Choose the Administrator role radio button
  const adminRadio = screen.getByRole('radio', { name: /administrator/i });
  act(() => adminRadio.click());

  // Click the demo‑password shortcut (always present in the UI)
  let demoBtn = screen.queryByRole('button', { name: /demo password/i });
  if (!demoBtn) {
    const demoToggle = screen.queryByRole('button', { name: /Demo Environment Access/i });
    if (demoToggle) {
      act(() => demoToggle.click());
    }
    demoBtn = screen.getByRole('button', { name: /demo password/i });
  }
  act(() => demoBtn.click());

  // Submit the login form
  const submit = screen.getByRole('button', { name: /sign in/i });
  act(() => submit.click());

  // Wait for login to complete and dashboard/queue to render
  await waitFor(() => {
    expect(screen.queryByRole('heading', { name: /sign in to your account/i })).not.toBeInTheDocument();
  });

  const currentUrl = new URL(window.location.href);
  const param = currentUrl.searchParams.get('incident');
  const valid = param && Number.isInteger(Number(param)) && Number(param) > 0 && Number(param) < 9007199254740990;
  if (!valid && !param) {
    const incidentsNav = await screen.findByRole('button', { name: /incidents queue/i });
    act(() => incidentsNav.click());
  }
}

// ---------------------------------------------------------------------------
// Test suite – URL navigation behaviours
// ---------------------------------------------------------------------------
describe('App‑level URL navigation (Phase 5.1‑A)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Start each test with a clean address bar
    window.history.replaceState(null, '', '/');
  });

  // 1️⃣ Initial hydration from ?incident=42 after login
  it('hydrates the selected incident from the URL after successful login', async () => {
    window.history.replaceState(null, '', '/?incident=42');
    await loginAsAdmin();
    // IncidentsPage will display the ticket label once loaded
    await waitFor(() => {
      expect(screen.getAllByText('INC-000042').length).toBeGreaterThan(0);
    });
    // URL must still contain the same param
    expect(new URL(window.location.href).searchParams.get('incident')).toBe('42');
  });

  // 2️⃣ Incident switching – real UI list picks incident 42 then 43
  it('updates the query parameter when navigating between incidents', async () => {
    await loginAsAdmin();
    const btn42 = await screen.findByRole('button', { name: /INC-000042/i });
    const btn43 = await screen.findByRole('button', { name: /INC-000043/i });
    act(() => btn42.click());
    await waitFor(() => {
      expect(new URL(window.location.href).searchParams.get('incident')).toBe('42');
    });
    act(() => btn43.click());
    await waitFor(() => {
      expect(new URL(window.location.href).searchParams.get('incident')).toBe('43');
    });
  });

  // 3️⃣ Refresh / remount restores incident from URL
  it('restores the selected incident after component remount (simulated refresh)', async () => {
    window.history.replaceState(null, '', '/?incident=42');
    const { unmount } = render(<App />);
    await loginAsAdmin();
    unmount();
    render(<App />);
    await loginAsAdmin();
    await waitFor(() => {
      expect(screen.getAllByText('INC-000042').length).toBeGreaterThan(0);
    });
    expect(new URL(window.location.href).searchParams.get('incident')).toBe('42');
  });

  // 4️⃣ Browser Back navigation
  it('updates selected incident when navigating back in history', async () => {
    await loginAsAdmin();
    const btn42 = await screen.findByRole('button', { name: /INC-000042/i });
    const btn43 = await screen.findByRole('button', { name: /INC-000043/i });
    act(() => btn42.click());
    act(() => btn43.click());
    expect(new URL(window.location.href).searchParams.get('incident')).toBe('43');
    act(() => window.history.back());
    await waitFor(() => {
      expect(screen.getAllByText('INC-000042').length).toBeGreaterThan(0);
    });
    expect(new URL(window.location.href).searchParams.get('incident')).toBe('42');
  });

  // 5️⃣ Browser Forward navigation
  it('updates selected incident when navigating forward in history', async () => {
    await loginAsAdmin();
    const btn42 = await screen.findByRole('button', { name: /INC-000042/i });
    const btn43 = await screen.findByRole('button', { name: /INC-000043/i });
    act(() => btn42.click());
    act(() => btn43.click());
    act(() => window.history.back());
    await waitFor(() => {
      expect(screen.getAllByText('INC-000042').length).toBeGreaterThan(0);
    });
    act(() => window.history.forward());
    await waitFor(() => {
      expect(screen.getAllByText('INC-000043').length).toBeGreaterThan(0);
    });
    expect(new URL(window.location.href).searchParams.get('incident')).toBe('43');
  });

  // 6️⃣ Navigating away clears the incident query parameter
  it('removes the incident query parameter when navigating away from Incidents page', async () => {
    await loginAsAdmin();
    const btn42 = await screen.findByRole('button', { name: /INC-000042/i });
    act(() => btn42.click());
    expect(new URL(window.location.href).searchParams.get('incident')).toBe('42');
    const dashboardNav = screen.getByRole('button', { name: /dashboard/i });
    act(() => dashboardNav.click());
    expect(new URL(window.location.href).searchParams.has('incident')).toBeFalsy();
  });

  // 7️⃣ Invalid incident IDs are ignored – UI shows no incident, state stays null.
  it('ignores invalid incident IDs from the URL', async () => {
    const invalid = ['0', '-5', '3.14', 'abc', '9007199254740993'];
    for (const p of invalid) {
      window.history.replaceState(null, '', `/?incident=${p}`);
      await loginAsAdmin();
      // No incident label should appear
      expect(screen.queryAllByText(/INC-/i).length).toBe(0);
      // The param remains in the address bar (App does not strip it) – we only check UI.
      expect(new URL(window.location.href).searchParams.get('incident')).toBe(p);
      const { unmount } = render(<App />);
      unmount();
    }
  });

  // 8️⃣ Duplicate‑history entry avoidance
  it('does not push a duplicate history entry when selecting the current incident again', async () => {
    await loginAsAdmin();
    const btn42 = await screen.findByRole('button', { name: /INC-000042/i });
    act(() => btn42.click());
    const len = window.history.length;
    act(() => btn42.click());
    expect(window.history.length).toBe(len);
    expect(new URL(window.location.href).searchParams.get('incident')).toBe('42');
  });
});
