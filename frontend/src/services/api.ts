const API_BASE = '/api';

export interface User {
  id: number;
  email: string;
  role: 'employee' | 'support_engineer' | 'administrator';
  access_token: string;
}

export interface DashboardStats {
  total_incidents: number;
  assigned_incidents: number;
  unassigned_incidents: number;
  open_incidents: number;
  in_progress_incidents: number;
  resolved_incidents: number;
  critical_incidents: number;
  approaching_sla_count: number;
  pending_approvals_count: number;
  average_resolution_time_min: number | null;
  sla_compliance_pct: number | null;
  sla_response_compliance_pct: number | null;
  sla_resolution_compliance_pct: number | null;
  sla_response_sample_count: number;
  sla_resolution_sample_count: number;
  sla_compliance_sample_count: number;
  ai_automation_rate_pct: number | null;
  ai_automation_sample_count: number;
  ai_automation_definition: string;
  active_agents_count: number;
  priority_distribution: Array<{ name: string; value: number }>;
  category_breakdown: Array<{ name: string; value: number }>;
  status_distribution: Array<{ name: string; value: number }>;
  team_workload: Array<{ team: string; active_incidents: number }>;
  trend_chart: Array<{ date: string; incidents: number; resolved: number }>;
  trend_date_range: { start_date: string; end_date: string };
  applied_date_range: { start_date: string | null; end_date: string | null };
  activity_timeline: Array<{
    id: string;
    action: string;
    status: string;
    duration_ms: number | null;
    time: string | null;
    summary: string | null;
  }>;
  recent_agent_runs: Array<{
    id: number;
    agent_name: string;
    incident_id: number | null;
    status: string;
    started_at: string | null;
    finished_at: string | null;
  }>;
  sla_breaches: Array<{
    id: number;
    title: string;
    severity: string;
    time_remaining_min: number;
    status: string;
    response_risk: 'breached' | 'at_risk' | null;
    resolution_risk: 'breached' | 'at_risk' | null;
  }>;
}

export interface OperationalInsight {
  key: string;
  kind: string;
  severity: 'critical' | 'warning' | 'informational';
  title: string;
  explanation: string;
  recommendation: string;
  evidence: Record<string, unknown>;
}

export interface SLAPolicy {
  id: number;
  name: string;
  priority_code: string | null;
  response_minutes: number;
  resolution_minutes: number;
  response_compliance_pct: number | null;
  response_sample_count: number;
  resolution_compliance_pct: number | null;
  resolution_sample_count: number;
  compliance_rate_pct: number | null;
  sample_count: number;
  status: 'No data' | 'Compliant' | 'At Risk';
}

export interface SLARisk {
  incident_id: number;
  ticket_id: string;
  priority: string;
  priority_code: string | null;
  status: string;
  response_due_at: string | null;
  resolution_due_at: string | null;
  response_minutes_remaining: number | null;
  resolution_minutes_remaining: number | null;
  response_risk: 'breached' | 'at_risk' | null;
  resolution_risk: 'breached' | 'at_risk' | null;
  risk: 'breached' | 'at_risk';
  deadline_type: 'response' | 'resolution';
  minutes_remaining: number;
  escalation_eligible: boolean;
  escalation_reason: string | null;
}

export interface SLATrendPoint {
  date: string;
  response_compliance_pct: number | null;
  resolution_compliance_pct: number | null;
  response_sample_count: number;
  resolution_sample_count: number;
  by_priority: Record<
    'P1' | 'P2' | 'P3' | 'P4',
    {
      response_compliance_pct: number | null;
      resolution_compliance_pct: number | null;
      response_sample_count: number;
      resolution_sample_count: number;
    }
  >;
}

export interface EmployeeTicket {
  ticket_id: string;
  record_id: number;
  ticket_type: 'incident' | 'service_request';
  category: string;
  priority: string;
  description: string;
  status: string;
  assigned_team: string | null;
  created_at: string | null;
  updated_at: string | null;
  response_due_at: string | null;
  resolution_due_at: string | null;
  resolution_summary: string | null;
  sla_status: 'breached' | 'on_track' | null;
}

export interface EmployeeProfile {
  id: number;
  email: string;
  role: User['role'];
  full_name: string | null;
  department: string | null;
  phone: string | null;
}

export interface EmployeePortalData {
  profile: EmployeeProfile;
  metrics: {
    total_tickets: number;
    open_tickets: number;
    in_progress_tickets: number;
    resolved_tickets: number;
    pending_service_requests: number;
    pending_approvals: number;
  };
  recent_tickets: EmployeeTicket[];
  recent_activity: Array<{
    id: number;
    title: string;
    message: string;
    notification_type: string;
    created_at: string;
    read: boolean;
  }>;
  announcements: Array<{ id: number; title: string; message: string; published_at: string }>;
  frequently_used_services: Array<{ category: string; request_count: number }>;
  service_catalog: Array<{ id: string; name: string }>;
  recommendations: string[];
  pending_approvals: Array<{
    id: number;
    request_type: string;
    status: string;
    created_at: string;
    decision_reason: string | null;
  }>;
  approvals: Array<{
    id: number;
    request_type: string;
    requested_action: string | null;
    status: string;
    created_at: string;
    decided_at: string | null;
    decision_reason: string | null;
    ticket_id: string | null;
  }>;
  assigned_assets: Array<{
    id: number;
    type: string;
    model: string | null;
    serial_number: string;
    assigned_at: string;
  }>;
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

async function authenticatedFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401 && accessToken) {
    setAccessToken(null);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('resolvex:auth-expired'));
    }
  }
  return response;
}

async function responseError(response: Response, fallback: string) {
  const body = await response.text();
  if (body) {
    try {
      const error = JSON.parse(body);
      if (typeof error.detail === 'string') return error.detail;
    } catch {
      return `${fallback} (HTTP ${response.status})`;
    }
  }
  return `${fallback} (HTTP ${response.status})`;
}

export interface AgentRunResponse {
  incident_id?: number;
  employee_id: number;
  user_message: string;
  intent: string;
  category: string;
  priority: string;
  retrieved_chunks: Array<{
    doc: string;
    chunk: string;
    score: number;
    category?: string;
  }>;
  diagnostics: Array<{
    tool: string;
    result: any;
    simulated: boolean;
  }>;
  proposed_resolution?: string;
  requires_approval: boolean;
  approval_id?: number;
  ticket_status: string;
  agent_trace: Array<{
    agent: string;
    summary: string;
    started_at: string;
    duration_ms: number;
    status: string;
  }>;
  errors: string[];
  is_demo: boolean;
  thread_id?: string;
  // Continuity Engine fields
  assigned_engineer_id?: number;
  assigned_engineer_name?: string;
  assigned_team?: string;
  lifecycle_phase?: string;
  exceptions?: Array<{
    type: string;
    exception_id?: number;
    action?: string;
    previous_engineer?: string;
    reassignment_count?: number;
    message?: string;
    sla_preserved?: boolean;
    error?: string;
  }>;
  employee_notification?: string;
}

export interface IncidentSummary {
  id: number;
  ticket_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  category: string;
  assigned_team: string | null;
  assigned_to: { id: number; name: string; email: string } | null;
  employee: { id: number; name: string; email: string; department: string | null };
  asset: {
    id: number;
    name: string;
    type: string;
    manufacturer: string | null;
    model: string | null;
    operating_system: string | null;
    status: string;
  } | null;
  created_at: string | null;
  updated_at: string | null;
  response_due_at: string | null;
  resolution_due_at: string | null;
  resolution_summary: string | null;
  lock_version?: number;
  sla: { risk: string; minutes_remaining: number | null; breached: boolean };
}

export interface IncidentDetail extends IncidentSummary {
  first_response_at: string | null;
  resolved_at: string | null;
  employee: IncidentSummary['employee'] & { assets: Array<NonNullable<IncidentSummary['asset']>> };
  history: Array<{
    event_type: string;
    from_value: string | null;
    to_value: string | null;
    details: string | null;
    created_at: string | null;
    actor: string | null;
  }>;
  comments: Array<{ content: string; created_at: string | null; author: string }>;
  related_incidents: Array<{ id: number; ticket_id: string; title: string; status: string }>;
  agent_runs: Array<{
    id: number;
    agent_name: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    steps: Array<{ step_name: string; status: string; summary: string | null }>;
  }>;
  mcp_calls: Array<{
    id: number;
    tool_name: string;
    calling_agent: string | null;
    status: string;
    duration_ms: number | null;
    permission_status: string | null;
    created_at: string | null;
  }>;
}

export interface IncidentPage {
  items: IncidentSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface IncidentFilters {
  priority?: string;
  category?: string;
  status?: string;
  team?: string;
  assignment?: 'all' | 'mine' | 'unassigned';
  sla_risk?: 'all' | 'on_track' | 'at_risk' | 'breached' | 'unknown';
  search?: string;
  sort_by?: 'created_at' | 'priority' | 'resolution_due_at';
  sort_order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export async function login(
  role: User['role'],
  email: string,
  password: string,
): Promise<User> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, email, password }),
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(await responseError(res, 'Login failed'));
    }
    return await res.json();
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error('Connection timed out connecting to backend server. Please verify backend is running on port 8000.');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function logout(): Promise<void> {
  const res = await authenticatedFetch(`${API_BASE}/auth/logout`, { method: 'POST' });
  if (!res.ok) throw new Error(await responseError(res, 'Logout failed'));
}

export async function runAgentChat(message: string, thread_id?: string): Promise<AgentRunResponse> {
  const res = await authenticatedFetch(`${API_BASE}/agent/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id }),
  });
  if (!res.ok) throw new Error(`Agent run failed: ${await res.text()}`);
  return res.json();
}

export async function getDashboardStats(
  startDate?: string,
  endDate?: string,
): Promise<DashboardStats> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const query = params.toString();
  const res = await authenticatedFetch(
    `${API_BASE}/stats/dashboard${query ? `?${query}` : ''}`,
  );
  if (!res.ok) throw new Error('Failed to fetch dashboard stats');
  return res.json();
}

export async function getOperationalInsights(
  startDate?: string,
  endDate?: string,
): Promise<{ source: 'database-rules'; generated_at: string; date_range: Record<string, string>; insights: OperationalInsight[] }> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const query = params.toString();
  const res = await authenticatedFetch(
    `${API_BASE}/stats/insights${query ? `?${query}` : ''}`,
  );
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch operational insights'));
  return res.json();
}

export async function getIncidents(filters: IncidentFilters = {}): Promise<IncidentPage> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== 'all') params.set(key, String(value));
  });
  const query = params.toString();
  const res = await authenticatedFetch(`${API_BASE}/incidents/${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error('Failed to fetch incidents');
  return res.json();
}

export async function getIncident(incidentId: number): Promise<IncidentDetail> {
  const res = await authenticatedFetch(`${API_BASE}/incidents/${incidentId}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch incident'));
  return res.json();
}

export async function getSupportUsers(): Promise<Array<{ id: number; name: string; email: string }>> {
  const res = await authenticatedFetch(`${API_BASE}/incidents/support-users`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch support engineers'));
  return res.json();
}

export async function updateIncident(
  incidentId: number,
  changes: {
    status?: string;
    priority?: string;
    assigned_team?: string | null;
    assigned_to_user_id?: number | null;
    asset_id?: number | null;
    resolution_summary?: string;
    resolution_verified?: boolean;
  },
): Promise<IncidentSummary> {
  const res = await authenticatedFetch(`${API_BASE}/incidents/${incidentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to update incident'));
  return res.json();
}

export async function investigateIncident(
  incidentId: number,
  message?: string,
): Promise<AgentRunResponse> {
  const res = await authenticatedFetch(`${API_BASE}/agent/investigate/${incidentId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(message ? { message } : {}),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Incident investigation failed'));
  return res.json();
}

export async function addIncidentComment(
  incidentId: number,
  content: string,
): Promise<{ id: number; content: string; created_at: string | null }> {
  const res = await authenticatedFetch(`${API_BASE}/incidents/${incidentId}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to add incident comment'));
  return res.json();
}

export async function executeMcpTool(
  toolName: string,
  incidentId: number,
  argumentsValue: Record<string, unknown>,
): Promise<{ status: string; duration_ms?: number; simulated?: boolean; result?: unknown; approval_id?: number; message?: string }> {
  const res = await authenticatedFetch(`${API_BASE}/mcp/tools/${encodeURIComponent(toolName)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ incident_id: incidentId, arguments: argumentsValue }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'MCP tool execution failed'));
  return res.json();
}

export async function getApprovals(): Promise<any[]> {
  const res = await authenticatedFetch(`${API_BASE}/approvals/`);
  if (!res.ok) throw new Error('Failed to fetch approvals');
  return res.json();
}

export async function approveRequest(approvalId: number, reason?: string): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/approvals/${approvalId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Approve action failed'));
  return res.json();
}

export async function rejectRequest(approvalId: number, reason?: string): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/approvals/${approvalId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Reject action failed'));
  return res.json();
}

export async function getAssets(): Promise<any[]> {
  const res = await authenticatedFetch(`${API_BASE}/assets/`);
  if (!res.ok) throw new Error('Failed to fetch assets');
  return res.json();
}

export async function getSLAPolicies(
  startDate?: string,
  endDate?: string,
): Promise<SLAPolicy[]> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const query = params.toString();
  const res = await authenticatedFetch(`${API_BASE}/sla/${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch SLA policies'));
  return res.json();
}

export async function getSLABreaches(options: {
  windowMinutes?: number;
  startDate?: string;
  endDate?: string;
} = {}): Promise<SLARisk[]> {
  const params = new URLSearchParams();
  if (options.windowMinutes !== undefined) params.set('window_minutes', String(options.windowMinutes));
  if (options.startDate) params.set('start_date', options.startDate);
  if (options.endDate) params.set('end_date', options.endDate);
  const query = params.toString();
  const res = await authenticatedFetch(`${API_BASE}/sla/breaches${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch SLA risks'));
  return res.json();
}

export async function getSLATrends(
  startDate?: string,
  endDate?: string,
): Promise<{ date_range: { start_date: string; end_date: string }; trend: SLATrendPoint[] }> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const query = params.toString();
  const res = await authenticatedFetch(`${API_BASE}/sla/trends${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch SLA compliance trends'));
  return res.json();
}

export async function getMCPStatus(): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/mcp/status`);
  if (!res.ok) throw new Error('Failed to fetch MCP status');
  return res.json();
}

export async function getMCPMetrics(): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/mcp/metrics`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch MCP metrics'));
  return res.json();
}

export async function getMCPCalls(options: { search?: string; status?: string } = {}): Promise<any[]> {
  const params = new URLSearchParams({ limit: '500' });
  if (options.search) params.set('search', options.search);
  if (options.status) params.set('status', options.status);
  const res = await authenticatedFetch(`${API_BASE}/mcp/calls?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch MCP calls');
  return res.json();
}

export async function getAgentRuns(options: { status?: string; incidentId?: number } = {}): Promise<any[]> {
  const params = new URLSearchParams();
  if (options.status) params.set('status', options.status);
  if (options.incidentId) params.set('incident_id', String(options.incidentId));
  const query = params.toString();
  const res = await authenticatedFetch(`${API_BASE}/agent/runs${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error('Failed to fetch agent runs');
  return res.json();
}

export async function getAgentRunMetrics(): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/agent/runs/metrics`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch agent metrics'));
  return res.json();
}

export async function getAgentRunDetail(runId: number): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/agent/runs/${runId}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch agent run details'));
  return res.json();
}

export async function getIncidentExecutionTimeline(incidentId: number): Promise<any[]> {
  const res = await authenticatedFetch(`${API_BASE}/agent/runs/timeline/${incidentId}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch execution timeline'));
  return res.json();
}

// ── Knowledge Base (admin route — no /api prefix) ──
const ADMIN_BASE = '';

export async function getKnowledgeDocs(): Promise<any[]> {
  const res = await authenticatedFetch(`${ADMIN_BASE}/admin/knowledge/`);
  if (!res.ok) throw new Error('Failed to fetch knowledge docs');
  return res.json();
}

export async function getKnowledgeStats(): Promise<any> {
  const res = await authenticatedFetch(`${ADMIN_BASE}/admin/knowledge/stats`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch knowledge statistics'));
  return res.json();
}

export async function getKnowledgeDoc(docId: string): Promise<any> {
  const res = await authenticatedFetch(`${ADMIN_BASE}/admin/knowledge/${encodeURIComponent(docId)}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch document preview'));
  return res.json();
}

export async function getKnowledgeChunks(docId: string): Promise<any> {
  const res = await authenticatedFetch(`${ADMIN_BASE}/admin/knowledge/${encodeURIComponent(docId)}/chunks`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch indexed chunks'));
  return res.json();
}

export async function evaluateKnowledgeRetrieval(payload: { query: string; category?: string; top_k?: number }): Promise<any> {
  const res = await authenticatedFetch(`${ADMIN_BASE}/admin/knowledge/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Knowledge retrieval evaluation failed'));
  return res.json();
}

export async function uploadKnowledgeDoc(file: File, category = 'general'): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('category', category);
  const res = await authenticatedFetch(`${ADMIN_BASE}/admin/knowledge/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}

export async function deleteKnowledgeDoc(docId: string): Promise<any> {
  const res = await authenticatedFetch(`${ADMIN_BASE}/admin/knowledge/${docId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Delete failed');
  return res.json();
}

export async function reindexKnowledge(): Promise<any> {
  const res = await authenticatedFetch(`${ADMIN_BASE}/admin/knowledge/reindex`, { method: 'POST' });
  if (!res.ok) throw new Error(await responseError(res, 'Reindex failed'));
  return res.json();
}

export async function getEmployeeDashboard(): Promise<EmployeePortalData> {
  const res = await authenticatedFetch(`${API_BASE}/employee/dashboard`);
  if (!res.ok) throw new Error(`Failed to load employee dashboard (HTTP ${res.status})`);
  return res.json();
}

export async function getEmployeeTickets(options: { status?: string; search?: string } = {}): Promise<EmployeeTicket[]> {
  const params = new URLSearchParams();
  if (options.status) params.set('status', options.status);
  if (options.search) params.set('search', options.search);
  const query = params.toString();
  const res = await authenticatedFetch(`${API_BASE}/employee/tickets${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error(`Failed to load tickets (HTTP ${res.status})`);
  return res.json();
}

export async function getEmployeeTicket(ticketId: string): Promise<EmployeeTicket & { conversation_history: Array<{ id: number; message: string; author: string; author_role: string; created_at: string }> }> {
  const res = await authenticatedFetch(`${API_BASE}/employee/tickets/${encodeURIComponent(ticketId)}`);
  if (!res.ok) throw new Error(`Failed to load ticket ${ticketId} (HTTP ${res.status})`);
  return res.json();
}

export async function addEmployeeTicketComment(ticketId: string, message: string): Promise<void> {
  const res = await authenticatedFetch(`${API_BASE}/employee/tickets/${encodeURIComponent(ticketId)}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Failed to add comment (HTTP ${res.status})`);
}

export async function reopenEmployeeTicket(ticketId: string): Promise<{ ticket_id: string; status: string }> {
  const res = await authenticatedFetch(`${API_BASE}/employee/tickets/${encodeURIComponent(ticketId)}/reopen`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to reopen ticket (HTTP ${res.status})`);
  return res.json();
}

export async function submitEmployeeResolutionFeedback(
  ticketId: string,
  resolved: boolean,
): Promise<{ ticket_id: string; status: string; feedback_recorded: boolean }> {
  const res = await authenticatedFetch(`${API_BASE}/employee/tickets/${encodeURIComponent(ticketId)}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolved }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Feedback could not be saved'));
  return res.json();
}

export async function createEmployeeServiceRequest(category: string, description: string): Promise<EmployeeTicket & { approval_id: number | null; requires_approval: boolean }> {
  const res = await authenticatedFetch(`${API_BASE}/employee/service-requests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category, description }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Service request failed'));
  return res.json();
}

export async function getEmployeeApprovals(): Promise<EmployeePortalData['pending_approvals']> {
  const res = await authenticatedFetch(`${API_BASE}/employee/approvals`);
  if (!res.ok) throw new Error(`Failed to load approvals (HTTP ${res.status})`);
  return res.json();
}

export async function updateEmployeeProfile(changes: Pick<EmployeeProfile, 'full_name' | 'phone'>): Promise<EmployeeProfile> {
  const res = await authenticatedFetch(`${API_BASE}/employee/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Profile update failed'));
  return res.json();
}

export async function markEmployeeNotificationRead(notificationId: number): Promise<void> {
  const res = await authenticatedFetch(`${API_BASE}/employee/notifications/${notificationId}/read`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to update notification (HTTP ${res.status})`);
}

export async function createAnnouncement(title: string, message: string): Promise<void> {
  const res = await authenticatedFetch(`${API_BASE}/admin/announcements/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, message }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Announcement could not be published'));
}

// ── Workforce & Continuity Engine ──────────────────────────────────────────

export interface EngineerAvailability {
  id: number;
  full_name: string;
  email: string;
  department: string | null;
  team: string;
  availability_status: string;
  is_available: boolean;
  availability_reason: string;
  skills: string[];
  current_workload: number;
  max_active_tickets: number;
  working_schedule: string | null;
  notes: string | null;
  is_simulated: boolean;
}

export interface AssignmentException {
  id: number;
  incident_id: number;
  exception_type: string;
  severity: string;
  attempted_engineer: string | null;
  resolved_engineer: string | null;
  action_taken: string | null;
  reason: string | null;
  employee_message: string | null;
  created_at: string | null;
  details: Record<string, unknown> | null;
}

export async function getWorkforceEngineers(): Promise<EngineerAvailability[]> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/engineers`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch engineer availability'));
  return res.json();
}

export async function getEligibleEngineers(params?: {
  category?: string;
  priority?: string;
  preferred_team?: string;
}): Promise<{
  category: string;
  priority: string;
  eligible_engineers: Array<{
    id: number;
    full_name: string;
    email: string;
    team: string;
    skills: string[];
    availability_status: 'available' | 'on_leave' | 'busy' | 'offline';
    current_workload: number;
    max_active_tickets: number;
    is_eligible: boolean;
    ineligibility_reason?: string | null;
    score?: number;
  }>;
}> {
  const query = new URLSearchParams();
  if (params?.category) query.set('category', params.category);
  if (params?.priority) query.set('priority', params.priority);
  if (params?.preferred_team) query.set('preferred_team', params.preferred_team);
  const res = await authenticatedFetch(`${API_BASE}/workforce/eligible-engineers${query.toString() ? `?${query.toString()}` : ''}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch eligible engineers'));
  return res.json();
}

export async function getEngineerAvailabilityDetail(userId: number): Promise<EngineerAvailability & {
  leave_start: string | null;
  leave_end: string | null;
  updated_at: string | null;
}> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/engineers/${userId}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch engineer detail'));
  return res.json();
}

export async function getIncidentExceptions(incidentId: number): Promise<AssignmentException[]> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/incidents/${incidentId}/exceptions`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch incident exceptions'));
  return res.json();
}

export async function claimIncident(incidentId: number, expectedLockVersion?: number): Promise<{ status: string; assigned_to: { id: number; name: string }; lock_version: number }> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/incidents/${incidentId}/claim`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_lock_version: expectedLockVersion ?? null }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to claim incident'));
  return res.json();
}

export async function rejectIncidentAssignment(incidentId: number, reason: string): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/incidents/${incidentId}/reject-assignment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to reject assignment'));
  return res.json();
}

export async function submitResolutionFeedback(incidentId: number, resolved: boolean, notes?: string): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/incidents/${incidentId}/resolution-feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolved, notes }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to submit resolution feedback'));
  return res.json();
}

export async function updateEngineerAvailability(
  userId: number,
  payload: {
    status?: string;
    working_schedule?: string;
    leave_start?: string | null;
    leave_end?: string | null;
    max_active_tickets?: number;
    skills?: string[];
    team?: string;
    notes?: string;
  },
): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/engineers/${userId}/availability`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to update engineer availability'));
  return res.json();
}

export async function listWorkforceExceptions(params?: {
  incident_id?: number;
  severity?: string;
  exception_type?: string;
  limit?: number;
}): Promise<AssignmentException[]> {
  const q = new URLSearchParams();
  if (params?.incident_id !== undefined) q.set('incident_id', String(params.incident_id));
  if (params?.severity) q.set('severity', params.severity);
  if (params?.exception_type) q.set('exception_type', params.exception_type);
  if (params?.limit) q.set('limit', String(params.limit));

  const url = `${API_BASE}/workforce/exceptions${q.toString() ? `?${q.toString()}` : ''}`;
  const res = await authenticatedFetch(url);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to list workforce exceptions'));
  const data = await res.json();
  return Array.isArray(data) ? data : (data.items || []);
}

export async function listAssignmentPolicies(): Promise<any[]> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/policies`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to list assignment policies'));
  return res.json();
}

export async function updateAssignmentPolicy(
  name: string,
  payload: {
    max_reassignment_attempts?: number;
    max_workload_per_engineer?: number;
    sla_at_risk_threshold_minutes?: number;
    auto_escalate_on_no_engineer?: boolean;
    require_skill_match?: boolean;
    escalation_timeout_minutes?: number;
    require_team_match?: boolean;
  },
): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/policies/${name}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to update assignment policy'));
  return res.json();
}

export async function getAssignmentDecision(
  category: string,
  priority: string = 'medium',
  preferredTeam?: string,
): Promise<any> {
  const q = new URLSearchParams({ category, priority });
  if (preferredTeam) q.set('preferred_team', preferredTeam);
  const res = await authenticatedFetch(`${API_BASE}/workforce/assignment-decision?${q.toString()}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to fetch assignment decision preview'));
  return res.json();
}

export async function listLabScenarios(): Promise<any[]> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/scenario-lab/scenarios`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to list scenario lab items'));
  return res.json();
}

export async function runLabScenario(scenarioId: string, customOptions?: {
  custom_description?: string;
  custom_category?: string;
  custom_priority?: string;
  simulate_delay_ms?: number;
}): Promise<any> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/scenario-lab/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario_id: scenarioId,
      ...(customOptions || {}),
    }),
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to execute lab scenario'));
  return res.json();
}

export async function runAllLabScenarios(): Promise<{
  batch_id: string;
  total_scenarios: number;
  passed_count: number;
  failed_count: number;
  warning_count: number;
  pass_rate_pct: number;
  total_duration_ms: number;
  results: any[];
  simulated: boolean;
  executed_at: string;
}> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/scenario-lab/run-all`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(await responseError(res, 'Failed to execute all lab scenarios'));
  return res.json();
}

export async function exportLabReport(format: 'json' | 'csv' = 'json'): Promise<Blob | any> {
  const res = await authenticatedFetch(`${API_BASE}/workforce/scenario-lab/export?format=${format}`);
  if (!res.ok) throw new Error(await responseError(res, 'Failed to export scenario lab report'));
  if (format === 'csv') {
    return res.blob();
  }
  return res.json();
}
