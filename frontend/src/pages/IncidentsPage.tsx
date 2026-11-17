import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Play,
  RefreshCw,
  Search,
  ShieldAlert,
  UserCheck,
  UserX,
  Wrench,
  X,
} from 'lucide-react';
import {
  addIncidentComment,
  claimIncident,
  executeMcpTool,
  getIncident,
  getIncidentExceptions,
  getIncidents,
  getMCPStatus,
  getSupportUsers,
  getWorkforceEngineers,
  getEligibleEngineers,
  rejectIncidentAssignment,
  IncidentDetail,
  IncidentFilters,
  IncidentPage,
  IncidentSummary,
  investigateIncident,
  updateIncident,
  AgentRunResponse,
  AssignmentException,
  EngineerAvailability,
  User,
} from '../services/api';
import { EngineerListbox } from '../components/EngineerListbox';
import { AssignEngineerModal } from '../components/AssignEngineerModal';

const PAGE_SIZE = 25;

export interface IncidentsPageProps {
  initialIncidentId?: number | null;
  onClearInitialId?: () => void;
  currentUser?: User;
}

export const IncidentsPage: React.FC<IncidentsPageProps> = ({
  initialIncidentId,
  onClearInitialId,
  currentUser,
}) => {
  const [page, setPage] = useState<IncidentPage>({ items: [], total: 0, limit: PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState<IncidentFilters>({ limit: PAGE_SIZE, offset: 0 });
  const [searchText, setSearchText] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(initialIncidentId ?? null);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [exceptions, setExceptions] = useState<AssignmentException[]>([]);
  const [exceptionsOpen, setExceptionsOpen] = useState(true);
  const [supportUsers, setSupportUsers] = useState<Array<{ id: number; name: string; email: string }>>([]);
  const [workforceEngineers, setWorkforceEngineers] = useState<EngineerAvailability[]>([]);
  const [eligibleIds, setEligibleIds] = useState<Set<number>>(new Set());
  const [toolNames, setToolNames] = useState<string[]>([]);
  const [selectedTool, setSelectedTool] = useState('');
  const [toolArguments, setToolArguments] = useState('{}');
  const [toolResult, setToolResult] = useState<Awaited<ReturnType<typeof executeMcpTool>> | null>(null);
  const [investigation, setInvestigation] = useState<AgentRunResponse | null>(null);
  const [assignee, setAssignee] = useState('');
  const [team, setTeam] = useState('');
  const [priority, setPriority] = useState('');
  const [status, setStatus] = useState('');
  const [resolutionSummary, setResolutionSummary] = useState('');
  const [verified, setVerified] = useState(false);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [claimBusy, setClaimBusy] = useState(false);
  const [claimSuccess, setClaimSuccess] = useState<string | null>(null);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectBusy, setRejectBusy] = useState(false);
  const [rejectError, setRejectError] = useState('');
  const [error, setError] = useState('');

  const loadIncidents = async (nextFilters = filters) => {
    try {
      setLoading(true);
      setError('');
      setPage(await getIncidents(nextFilters));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load incidents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadIncidents();
    getSupportUsers()
      .then(setSupportUsers)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Failed to load support engineers.'));
    getWorkforceEngineers()
      .then(setWorkforceEngineers)
      .catch(() => { });
    getMCPStatus()
      .then((response) => {
        const names = (response.tools || []).map((tool: { name: string }) => tool.name);
        setToolNames(names);
        setSelectedTool(names[0] || '');
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Failed to load MCP tools.'));
    // Fetch eligible engineer IDs for assignment listbox
    getEligibleEngineers()
      .then((resp) => {
        const ids = (resp?.eligible_engineers ?? []).map((eng) => eng.id);
        setEligibleIds(new Set(ids));
      })
      .catch(() => setEligibleIds(new Set()));
  }, []);

  useEffect(() => {
    if (initialIncidentId) {
      setSelectedId(initialIncidentId);
    } else {
      const url = new URL(window.location.href);
      const param = url.searchParams.get('incident');
      if (param) {
        const id = Number(param);
        if (Number.isInteger(id) && id > 0 && id < 9007199254740990) {
          setSelectedId(id);
        }
      }
    }
  }, [initialIncidentId]);

  useEffect(() => {
    const handlePopState = () => {
      const url = new URL(window.location.href);
      const param = url.searchParams.get('incident');
      if (param) {
        const id = Number(param);
        if (Number.isInteger(id) && id > 0 && id < 9007199254740990) {
          setSelectedId(id);
        } else {
          setSelectedId(null);
        }
      } else {
        setSelectedId(null);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleSelectIncident = (id: number) => {
    if (selectedId === id) return;
    setSelectedId(id);
    const url = new URL(window.location.href);
    if (url.searchParams.get('incident') !== String(id)) {
      url.searchParams.set('incident', String(id));
      window.history.pushState(null, '', url.toString());
    }
  };

  useEffect(() => {
    if (selectedId === null) {
      setDetail(null);
      setInvestigation(null);
      setExceptions([]);
      setExceptionsOpen(false);
      return;
    }
    let active = true;
    getIncident(selectedId)
      .then((record) => {
        if (!active) return;
        setDetail(record);
        setAssignee(record.assigned_to ? String(record.assigned_to.id) : '');
        setTeam(record.assigned_team || '');
        setPriority(record.priority);
        setStatus(record.status);
        setResolutionSummary(record.resolution_summary || '');
        setVerified(false);
        setToolArguments(JSON.stringify({ ticket_id: record.id }, null, 2));
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Failed to load incident details.'));
    getIncidentExceptions(selectedId)
      .then((excs) => { if (active) setExceptions(excs); })
      .catch(() => { /* exceptions are non-critical */ });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const handleClaim = async () => {
    if (!detail) return;
    setClaimBusy(true);
    setClaimSuccess(null);
    setError('');
    try {
      await claimIncident(detail.id, detail.lock_version);
      setClaimSuccess(`Confirmed: You claimed ${detail.ticket_id}.`);
      await refreshSelected();
    } catch (caught: any) {
      const msg = caught instanceof Error ? caught.message : String(caught);
      if (msg.includes('409') || msg.toLowerCase().includes('conflict')) {
        setError('Incident was modified by another user. Refreshing...');
        await refreshSelected();
      } else {
        setError(msg);
      }
    } finally {
      setClaimBusy(false);
    }
  };

  const handleReject = async () => {
    if (!detail) return;
    if (rejectReason.trim().length < 5) {
      setRejectError('A meaningful reason (at least 5 characters) is required to decline assignment.');
      return;
    }
    setRejectBusy(true);
    setRejectError('');
    try {
      await rejectIncidentAssignment(detail.id, rejectReason.trim());
      setRejectModalOpen(false);
      setRejectReason('');
      setClaimSuccess('Assignment declined and re-routed to next eligible engineer.');
      await refreshSelected();
    } catch (caught) {
      setRejectError(caught instanceof Error ? caught.message : 'Failed to decline assignment.');
    } finally {
      setRejectBusy(false);
    }
  };

  const applyFilters = (updates: Partial<IncidentFilters>) => {
    const next = { ...filters, ...updates, offset: 0 };
    setFilters(next);
    void loadIncidents(next);
  };

  const refreshSelected = async () => {
    await loadIncidents();
    if (selectedId !== null) {
      const refreshed = await getIncident(selectedId);
      setDetail(refreshed);
      setAssignee(refreshed.assigned_to ? String(refreshed.assigned_to.id) : '');
      setTeam(refreshed.assigned_team || '');
      setPriority(refreshed.priority);
      setStatus(refreshed.status);
      setResolutionSummary(refreshed.resolution_summary || '');
    }
  };

  const saveIncident = async () => {
    if (!detail) return;
    if (status === 'resolved' && (!verified || !resolutionSummary.trim())) {
      setError('Resolution requires notes and confirmation that the outcome was verified.');
      return;
    }
    try {
      setBusy(true);
      setError('');
      await updateIncident(detail.id, {
        status,
        priority,
        assigned_team: team.trim() || null,
        assigned_to_user_id: assignee ? Number(assignee) : null,
        resolution_summary: status === 'resolved' ? resolutionSummary.trim() : undefined,
        resolution_verified: status === 'resolved' ? verified : undefined,
      });
      await refreshSelected();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to save incident.');
    } finally {
      setBusy(false);
    }
  };

  const runInvestigation = async () => {
    if (!detail) return;
    try {
      setBusy(true);
      setError('');
      setInvestigation(await investigateIncident(detail.id));
      await refreshSelected();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Incident investigation failed.');
    } finally {
      setBusy(false);
    }
  };

  const runTool = async () => {
    if (!detail || !selectedTool) return;
    try {
      const args: unknown = JSON.parse(toolArguments);
      if (!args || Array.isArray(args) || typeof args !== 'object') {
        throw new Error('Tool parameters must be a JSON object.');
      }
      setBusy(true);
      setError('');
      setToolResult(await executeMcpTool(selectedTool, detail.id, args as Record<string, unknown>));
      await refreshSelected();
    } catch (caught) {
      setToolResult(null);
      setError(caught instanceof Error ? caught.message : 'MCP tool execution failed.');
    } finally {
      setBusy(false);
    }
  };

  const addComment = async () => {
    if (!detail || !comment.trim()) return;
    try {
      setBusy(true);
      setError('');
      await addIncidentComment(detail.id, comment.trim());
      setComment('');
      setDetail(await getIncident(detail.id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to add comment.');
    } finally {
      setBusy(false);
    }
  };

  const movePage = (offset: number) => {
    const next = { ...filters, offset };
    setFilters(next);
    void loadIncidents(next);
  };

  const selectedEng = workforceEngineers.find((e) => String(e.id) === assignee);

  return (
    <div className="h-full overflow-y-auto bg-slate-50 p-5 lg:p-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Incident Operations</h2>
          <p className="mt-1 text-xs text-slate-500">Investigate, assign, and resolve incidents with auditable evidence.</p>
        </div>
        <button onClick={() => void refreshSelected()} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </header>

      {error && (
        <div role="alert" className="mb-4 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {claimSuccess && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
          <span className="flex items-center gap-1.5 font-semibold">
            <CheckCircle className="h-4 w-4 text-emerald-600 shrink-0" /> {claimSuccess}
          </span>
          <button onClick={() => setClaimSuccess(null)} className="text-emerald-700 hover:text-emerald-900">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <section className="mb-5 grid grid-cols-1 gap-2 rounded-xl border border-slate-200 bg-white p-3 md:grid-cols-2 xl:grid-cols-4">
        <form
          className="flex items-center gap-2 rounded-lg border border-slate-200 px-2"
          onSubmit={(event) => {
            event.preventDefault();
            applyFilters({ search: searchText || undefined });
          }}
        >
          <Search className="h-4 w-4 text-slate-400" />
          <input aria-label="Search incidents" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Search tickets or employees" className="min-w-0 flex-1 py-2 text-xs outline-none" />
          <button type="submit" className="text-xs font-semibold text-blue-700">Search</button>
        </form>
        <select aria-label="Filter by priority" value={filters.priority || 'all'} onChange={(event) => applyFilters({ priority: event.target.value })} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
          <option value="all">All priorities</option>
          {['critical', 'high', 'medium', 'low'].map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
        <select aria-label="Filter by status" value={filters.status || 'all'} onChange={(event) => applyFilters({ status: event.target.value })} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
          <option value="all">All statuses</option>
          {['open', 'assigned', 'investigating', 'in_progress', 'pending_approval', 'resolved', 'closed'].map((value) => <option key={value} value={value}>{value.replace(/_/g, ' ')}</option>)}
        </select>
        <select aria-label="Filter by category" value={filters.category || 'all'} onChange={(event) => applyFilters({ category: event.target.value })} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
          <option value="all">All categories</option>
          {['network', 'vpn', 'software', 'hardware', 'server', 'general'].map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
        <div className="flex gap-2">
          <select aria-label="Filter by assignment" value={filters.assignment || 'all'} onChange={(event) => applyFilters({ assignment: event.target.value as IncidentFilters['assignment'] })} className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
            <option value="all">All assignments</option><option value="mine">Assigned to me</option><option value="unassigned">Unassigned</option>
          </select>
          <select aria-label="Filter by SLA risk" value={filters.sla_risk || 'all'} onChange={(event) => applyFilters({ sla_risk: event.target.value as IncidentFilters['sla_risk'] })} className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
            <option value="all">All SLA states</option><option value="at_risk">At risk</option><option value="breached">Breached</option><option value="unknown">No deadline</option>
          </select>
        </div>
        <input aria-label="Filter by support team" value={filters.team || ''} onChange={(event) => setFilters((current) => ({ ...current, team: event.target.value || undefined }))} onKeyDown={(event) => { if (event.key === 'Enter') applyFilters({ team: filters.team || undefined }); }} placeholder="Team name; press Enter" className="rounded-lg border border-slate-200 px-3 py-2 text-xs" />
      </section>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(440px,0.9fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <h3 className="text-sm font-bold text-slate-800">Incident queue <span className="ml-1 font-normal text-slate-400">({page.total})</span></h3>
            <div className="flex gap-2">
              <select aria-label="Sort incidents" value={filters.sort_by || 'created_at'} onChange={(event) => applyFilters({ sort_by: event.target.value as IncidentFilters['sort_by'] })} className="rounded border border-slate-200 bg-white px-2 py-1 text-xs">
                <option value="created_at">Newest</option><option value="priority">Priority</option><option value="resolution_due_at">SLA deadline</option>
              </select>
              <button onClick={() => applyFilters({ sort_order: filters.sort_order === 'asc' ? 'desc' : 'asc' })} className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600">{filters.sort_order === 'asc' ? 'Ascending' : 'Descending'}</button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <tr><th className="px-3 py-3">Ticket</th><th className="px-3 py-3">Reporter</th><th className="px-3 py-3">Priority / SLA</th><th className="px-3 py-3">Team / Assignee</th><th className="px-3 py-3">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr><td colSpan={5} className="p-8 text-center text-slate-500">Loading incident records…</td></tr>
                ) : page.items.length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-slate-500">No incidents match these filters.</td></tr>
                ) : page.items.map((incident) => (
                  <IncidentRow key={incident.id} incident={incident} selected={selectedId === incident.id} onSelect={() => handleSelectIncident(incident.id)} />
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
            <span>{page.total ? `${page.offset + 1}–${Math.min(page.offset + page.limit, page.total)} of ${page.total}` : '0 incidents'}</span>
            <div className="flex gap-2">
              <button aria-label="Previous page" disabled={page.offset === 0} onClick={() => movePage(Math.max(0, page.offset - PAGE_SIZE))} className="rounded border border-slate-200 p-1 disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button>
              <button aria-label="Next page" disabled={page.offset + page.limit >= page.total} onClick={() => movePage(page.offset + PAGE_SIZE)} className="rounded border border-slate-200 p-1 disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          {!detail ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">Select an incident to open its investigation workspace.</div>
          ) : (
            <>
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs font-bold text-blue-700">{detail.ticket_id}</p>
                    <h3 className="mt-1 text-base font-bold text-slate-900">{detail.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{detail.description}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${detail.sla?.risk === 'breached' ? 'bg-rose-100 text-rose-700' : detail.sla?.risk === 'at_risk' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                      SLA {detail.sla?.risk ? detail.sla.risk.replace(/_/g, ' ') : 'on track'}{detail.sla?.minutes_remaining !== undefined && detail.sla?.minutes_remaining !== null ? ` · ${detail.sla.minutes_remaining}m` : ''}
                    </span>
                    <button
                      type="button"
                      onClick={() => { setSelectedId(null); onClearInitialId?.(); }}
                      className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
                      aria-label="Close workspace"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs text-slate-600 sm:grid-cols-3">
                  <Info label="Reporter" value={detail.employee?.name || 'Unassigned'} />
                  <Info label="Department" value={detail.employee?.department || 'Not recorded'} />
                  <Info label="Created" value={formatDate(detail.created_at)} />
                  <Info label="Category" value={detail.category} />
                  <Info label="Asset" value={detail.asset?.name || 'Not linked'} />
                  <Info label="Deadline" value={formatDate(detail.resolution_due_at)} />
                  <Info label="Assigned Engineer" value={detail.assigned_to?.name || 'Unassigned'} />
                  <Info label="Support Team" value={detail.assigned_team || 'Unassigned'} />
                </div>
                {(detail.employee?.assets?.length ?? 0) > 0 && (
                  <div className="mt-4 border-t border-slate-100 pt-3">
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">Reporter assets</p>
                    <div className="flex flex-wrap gap-2">{detail.employee?.assets?.map((asset) => <span key={asset.id} className="rounded bg-slate-100 px-2 py-1 text-[11px] text-slate-700">{asset.name} · {asset.manufacturer || 'Unknown maker'} {asset.model || ''} · {asset.status}</span>)}</div>
                  </div>
                )}
                <div className="mt-4 border-t border-amber-100 pt-3">
                  <button
                    type="button"
                    onClick={() => setExceptionsOpen((o) => !o)}
                    className="flex w-full items-center justify-between text-[11px] font-semibold text-amber-900"
                  >
                    <span className="flex items-center gap-1.5">
                      <ShieldAlert className="h-4 w-4 text-amber-600" />
                      Assignment &amp; Continuity Exceptions ({exceptions.length})
                    </span>
                    <span className="text-slate-400">{exceptionsOpen ? '▲' : '▼'}</span>
                  </button>
                  {exceptionsOpen && (
                    <div className="mt-2 space-y-2">
                      {exceptions.length === 0 ? (
                        <p className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs text-slate-400 italic">
                          No continuity exceptions recorded for this incident.
                        </p>
                      ) : (
                        exceptions.map((exc) => (
                          <div key={exc.id} className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs">
                            <div className="flex items-start justify-between gap-2">
                              <span className="font-semibold text-amber-900">{exc.exception_type.replace(/_/g, ' ')}</span>
                              <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${exc.severity === 'high' || exc.severity === 'critical' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'}`}>
                                {exc.severity}
                              </span>
                            </div>
                            {exc.action_taken && <p className="mt-1 font-medium text-slate-800">Action: {exc.action_taken}</p>}
                            {exc.attempted_engineer && (
                              <p className="mt-0.5 text-slate-600">Reassignment: {exc.attempted_engineer} → {exc.resolved_engineer || 'Manager Escalation'}</p>
                            )}
                            {exc.reason && <p className="mt-1 text-slate-600">{exc.reason}</p>}
                            {exc.employee_message && (
                              <div className="mt-2 rounded bg-blue-50 border border-blue-100 p-2 text-blue-900">
                                <p className="font-semibold text-[10px] uppercase tracking-wide mb-0.5">Employee Notification Dispatched</p>
                                <p className="text-[11px]">{exc.employee_message}</p>
                              </div>
                            )}
                            <p className="mt-1 text-[10px] text-slate-400">{formatDate(exc.created_at)}</p>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-800">Assignment and resolution</h3>
                    <p className="text-[11px] text-slate-500">Assign to qualified personnel, claim ownership, or resolve with verification.</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={busy || claimBusy}
                      onClick={() => void handleClaim()}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 text-xs font-semibold shadow-sm transition disabled:opacity-50"
                    >
                      <UserCheck className="w-3.5 h-3.5" />
                      {claimBusy ? 'Claiming...' : 'Claim Incident'}
                    </button>
                    {detail.assigned_to && (
                      <button
                        type="button"
                        disabled={busy || rejectBusy}
                        onClick={() => { setRejectModalOpen(true); setRejectReason(''); setRejectError(''); }}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50"
                      >
                        <UserX className="w-3.5 h-3.5" />
                        Decline
                      </button>
                    )}
                    <button
                      disabled={busy}
                      onClick={() => void saveIncident()}
                      className="rounded-lg bg-blue-700 hover:bg-blue-800 px-3 py-1.5 text-xs font-semibold text-white shadow-sm disabled:opacity-50"
                    >
                      Save changes
                    </button>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="text-xs font-medium text-slate-600" htmlFor="priority-select">Priority</label>
                  <select id="priority-select" value={priority} onChange={(e) => setPriority(e.target.value)} className="mt-1 w-full rounded border border-slate-200 bg-white px-2 py-2">
                    {['critical', 'high', 'medium', 'low'].map(v => <option key={v} value={v}>{v}</option>)}
                  </select>

                  <label className="text-xs font-medium text-slate-600" htmlFor="status-select">Status</label>
                  <select id="status-select" value={status} onChange={(e) => setStatus(e.target.value)} className="mt-1 w-full rounded border border-slate-200 bg-white px-2 py-2">
                    {['open', 'assigned', 'investigating', 'in_progress', 'pending_approval', 'resolved', 'closed', 'cancelled'].map(v => <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>)}
                  </select>
                  {/* Engineer assignment using custom listbox */}
                  <div className="flex items-center justify-between">
                    <label id="engineer-select-label" className="text-xs font-medium text-slate-600" htmlFor="engineer-select">
                      Assigned engineer
                    </label>
                    <button
                      type="button"
                      disabled={busy || claimBusy}
                      onClick={() => setAssignModalOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-2 py-1 text-xs text-slate-700 hover:bg-slate-200"
                    >
                      Assign Engineer…
                    </button>
                  </div>
                  <EngineerListbox
                    engineers={workforceEngineers}
                    eligibleIds={eligibleIds}
                    selectedId={assignee}
                    onChange={setAssignee}
                    labelId="engineer-select-label"
                  />
                  <label className="text-xs font-medium text-slate-600">Support team
                    <input value={team} onChange={(event) => setTeam(event.target.value)} className="mt-1 w-full rounded border border-slate-200 px-2 py-2" />
                  </label>
                </div>

                {selectedEng && (
                  <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 p-2.5 text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-slate-800">{selectedEng.full_name} ({selectedEng.team})</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${selectedEng.availability_status === 'available' ? 'bg-emerald-100 text-emerald-700' : selectedEng.availability_status === 'on_leave' ? 'bg-amber-100 text-amber-700' : 'bg-orange-100 text-orange-700'}`}>
                        {selectedEng.availability_status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <span className="text-[11px] text-slate-500">Workload: {selectedEng.current_workload}/{selectedEng.max_active_tickets} active tickets</span>
                      <div className="h-1.5 w-20 rounded-full bg-slate-200 overflow-hidden">
                        <div className={`h-full rounded-full ${selectedEng.current_workload >= selectedEng.max_active_tickets ? 'bg-rose-500' : selectedEng.current_workload >= selectedEng.max_active_tickets * 0.7 ? 'bg-amber-400' : 'bg-emerald-500'}`} style={{ width: `${Math.min(100, (selectedEng.current_workload / (selectedEng.max_active_tickets || 1)) * 100)}%` }} />
                      </div>
                      <span className="text-[11px] text-slate-400">· Skills: {selectedEng.skills.join(', ')}</span>
                    </div>
                  </div>
                )}
                {status === 'resolved' && (
                  <div className="mt-3 space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <label className="block text-xs font-medium text-slate-700">Resolution notes
                      <textarea value={resolutionSummary} onChange={(event) => setResolutionSummary(event.target.value)} rows={3} className="mt-1 w-full rounded border border-amber-200 bg-white p-2" />
                    </label>
                    <label className="flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} /> I verified the resolution outcome.</label>
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div><h3 className="text-sm font-bold text-slate-800">AI investigation</h3><p className="text-[11px] text-slate-500">Evidence-based findings; recommendations are not confirmed fixes.</p></div>
                  <button disabled={busy} onClick={() => void runInvestigation()} className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-800 disabled:opacity-50"><Play className="h-3.5 w-3.5" /> Investigate</button>
                </div>
                {investigation && (
                  <div className="space-y-3 text-xs">
                    {investigation.is_demo && <p className="rounded bg-amber-50 px-2 py-1 font-semibold text-amber-800">DEMO MODE: simulated AI workflow</p>}
                    <div className="rounded-lg bg-violet-50 p-3"><strong>AI hypothesis · {investigation.category} / {investigation.priority}</strong><p className="mt-1 text-slate-700">{investigation.proposed_resolution || 'No recommendation returned.'}</p></div>
                    {investigation.errors.length > 0 && <div role="alert" className="rounded bg-rose-50 p-2 text-rose-800">{investigation.errors.join(' · ')}</div>}
                    {investigation.retrieved_chunks.map((source, index) => <div key={`${source.doc}-${index}`} className="rounded border border-slate-200 p-2"><p className="font-semibold text-slate-800">{source.doc} <span className="font-normal text-slate-500">score {source.score.toFixed(3)}</span></p><p className="mt-1 text-slate-600">{source.chunk}</p></div>)}
                    {investigation.diagnostics.map((diagnostic, index) => <div key={`${diagnostic.tool}-${index}`} className="rounded border border-slate-200 p-2"><div className="flex items-center justify-between font-semibold text-slate-800"><span>{diagnostic.tool}</span>{diagnostic.simulated && <span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] text-amber-800">Simulated</span>}</div><pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-[11px] text-slate-600">{JSON.stringify(diagnostic.result, null, 2)}</pre></div>)}
                    <ol className="space-y-2 border-l border-slate-200 pl-3">{investigation.agent_trace.map((step, index) => <li key={`${step.agent}-${index}`}><strong className="text-slate-700">{step.agent}</strong><p className="text-slate-500">{step.summary}</p></li>)}</ol>
                  </div>
                )}
                {!investigation && <button onClick={() => void runInvestigation()} disabled={busy} className="text-xs font-semibold text-blue-700">Start a read-only investigation</button>}
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-center gap-2"><Wrench className="h-4 w-4 text-blue-700" /><h3 className="text-sm font-bold text-slate-800">MCP operations</h3></div>
                <p className="mb-3 text-[11px] text-slate-500">Sensitive escalation is routed to approval. Ticket resolution requires the verified resolution workflow.</p>
                <div className="flex flex-wrap gap-2">
                  <select aria-label="MCP tool" value={selectedTool} onChange={(event) => setSelectedTool(event.target.value)} className="min-w-0 flex-1 rounded border border-slate-200 bg-white px-2 py-2 text-xs">{toolNames.map((name) => <option key={name}>{name}</option>)}</select>
                  <button disabled={busy || !selectedTool} onClick={() => void runTool()} className="rounded-lg bg-slate-800 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">Execute</button>
                </div>
                <textarea aria-label="MCP tool parameters" value={toolArguments} onChange={(event) => setToolArguments(event.target.value)} rows={3} className="mt-2 w-full rounded border border-slate-200 p-2 font-mono text-[11px]" />
                {toolResult && <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3 text-xs"><div className="flex justify-between font-semibold"><span>{toolResult.status}{toolResult.duration_ms !== undefined ? ` · ${toolResult.duration_ms}ms` : ''}</span>{toolResult.simulated && <span className="text-amber-700">Simulated</span>}</div>{toolResult.approval_id && <p className="mt-1">Pending approval #{toolResult.approval_id}</p>}<pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap">{JSON.stringify(toolResult.result || toolResult.message, null, 2)}</pre></div>}
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="mb-3 text-sm font-bold text-slate-800">History and communication</h3>
                <div className="mb-4 space-y-2">
                  {detail.history?.map((entry, index) => <div key={`${entry.event_type}-${index}`} className="border-l-2 border-blue-200 pl-3 text-xs"><strong>{entry.event_type.replace(/_/g, ' ')}</strong><p className="text-slate-500">{entry.from_value || '—'} → {entry.to_value || entry.details || '—'} · {entry.actor || 'System'} · {formatDate(entry.created_at)}</p></div>)}
                  {detail.comments?.map((entry, index) => <div key={`comment-${index}`} className="rounded bg-slate-50 p-2 text-xs"><p>{entry.content}</p><p className="mt-1 text-slate-400">{entry.author} · {formatDate(entry.created_at)}</p></div>)}
                  {(detail.history?.length ?? 0) === 0 && (detail.comments?.length ?? 0) === 0 && <p className="text-xs text-slate-500">No recorded history or comments.</p>}
                </div>
                <div className="flex gap-2"><input aria-label="Support comment" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Send an employee update" className="min-w-0 flex-1 rounded border border-slate-200 px-3 py-2 text-xs" /><button disabled={busy || !comment.trim()} onClick={() => void addComment()} className="rounded bg-blue-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">Comment</button></div>
              </div>

              {((detail.agent_runs?.length ?? 0) > 0 || (detail.mcp_calls?.length ?? 0) > 0) && (
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="mb-3 text-sm font-bold text-slate-800">Execution audit</h3>
                  <div className="space-y-2 text-xs">
                    {detail.agent_runs?.map((run) => <div key={run.id} className="rounded border border-slate-100 p-2"><p className="font-semibold">{run.agent_name} · {run.status}</p><p className="text-slate-500">{formatDate(run.started_at)} {run.finished_at ? `– ${formatDate(run.finished_at)}` : ''}</p>{run.steps?.map((step, index) => <p key={`${run.id}-${index}`} className="mt-1 text-slate-600">{step.step_name}: {step.summary || step.status}</p>)}</div>)}
                    {detail.mcp_calls?.map((call) => <div key={call.id} className="flex flex-wrap justify-between gap-2 rounded border border-slate-100 p-2"><span>{call.calling_agent || 'Agent'} · {call.tool_name} · {call.status}</span><span className="text-slate-500">{call.duration_ms ?? '—'}ms · {call.permission_status || 'unknown'} · {formatDate(call.created_at)}</span></div>)}
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </div>

      {assignModalOpen && detail && (
        <AssignEngineerModal
          incidentId={detail.id}
          currentEngineerId={detail.assigned_to?.id}
          engineers={workforceEngineers}
          eligibleIds={eligibleIds}
          lockVersion={detail.lock_version ?? 1}
          onClose={() => setAssignModalOpen(false)}
          onAssign={async (engineerId?: number) => {
            await updateIncident(detail.id, {
              assigned_to_user_id: engineerId ?? null,
            });
            await refreshSelected();
          }}
        />
      )}

      {rejectModalOpen && detail && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Decline incident assignment">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-bold text-slate-900 text-base">Decline Assignment</h3>
                <p className="text-xs text-slate-500 mt-0.5">{detail.ticket_id} · {detail.title}</p>
              </div>
              <button onClick={() => setRejectModalOpen(false)} aria-label="Close dialog"><X className="w-5 h-5 text-slate-400" /></button>
            </div>
            <p className="text-xs text-slate-600">
              Declining this incident will log an operational exception and trigger intelligent continuity re-routing to the next eligible engineer.
            </p>
            {rejectError && <p role="alert" className="text-xs text-rose-700 bg-rose-50 border border-rose-200 p-2 rounded">{rejectError}</p>}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Reason for declining (mandatory, minimum 5 characters):
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={3}
                placeholder="e.g., Currently overloaded with P1 incident investigation..."
                className="w-full text-xs border border-slate-200 rounded-lg p-2.5 outline-none focus:ring-1 focus:ring-rose-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                disabled={rejectBusy}
                onClick={() => setRejectModalOpen(false)}
                className="px-3 py-1.5 text-xs font-semibold text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={rejectBusy || rejectReason.trim().length < 5}
                onClick={() => void handleReject()}
                className="px-3 py-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm disabled:opacity-50"
              >
                {rejectBusy ? 'Declining...' : 'Confirm Decline'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

function IncidentRow({ incident, selected, onSelect }: { incident: IncidentSummary; selected: boolean; onSelect: () => void }) {
  const riskClass = incident.sla?.risk === 'breached' ? 'text-rose-700' : incident.sla?.risk === 'at_risk' ? 'text-amber-700' : 'text-slate-500';
  return (
    <tr className={selected ? 'bg-blue-50' : 'hover:bg-slate-50'}>
      <td className="px-3 py-3"><button onClick={onSelect} className="text-left"><span className="font-mono font-bold text-blue-700">{incident.ticket_id}</span><span className="mt-1 block max-w-48 truncate text-[11px] text-slate-600">{incident.title}</span></button></td>
      <td className="px-3 py-3"><p className="font-medium text-slate-800">{incident.employee?.name || 'Unknown'}</p><p className="text-[10px] text-slate-500">{incident.employee?.department || incident.employee?.email || '—'}</p></td>
      <td className="px-3 py-3"><span className="font-bold uppercase">{incident.priority}</span><span className={`mt-1 flex items-center gap-1 text-[10px] ${riskClass}`}><Clock className="h-3 w-3" />{incident.sla?.risk ? incident.sla.risk.replace(/_/g, ' ') : 'unknown'}</span></td>
      <td className="px-3 py-3"><p>{incident.assigned_team || 'Unassigned team'}</p><p className="text-[10px] text-slate-500">{incident.assigned_to?.name || 'No engineer'}</p></td>
      <td className="px-3 py-3"><span className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-700"><CheckCircle className="h-3 w-3" />{incident.status ? incident.status.replace(/_/g, ' ') : 'new'}</span></td>
    </tr>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return <div><p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p><p className="mt-1 truncate font-medium text-slate-700">{value}</p></div>;
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded';
}
