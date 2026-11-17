import React, { useEffect, useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, Node, Edge, MarkerType } from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Clock3,
  ExternalLink,
  FlaskConical,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Sliders,
  Terminal,
  Users,
  X,
} from 'lucide-react';
import {
  getAgentRunDetail,
  getAgentRunMetrics,
  getAgentRuns,
  getIncidentExecutionTimeline,
  getWorkforceEngineers,
  listAssignmentPolicies,
  listWorkforceExceptions,
  updateAssignmentPolicy,
  EngineerAvailability,
  AssignmentException,
  User,
} from '../services/api';

interface CommandCenterPageProps {
  onNavigate?: (page: string, incidentId?: number) => void;
  currentUser?: User;
}

const initialNodes: Node[] = [
  {
    id: 'triage',
    position: { x: 20, y: 100 },
    data: { label: '🎯 Triage Agent\n(Classification & Priority)' },
    style: { background: '#EFF6FF', border: '2px solid #2563EB', borderRadius: '12px', fontWeight: 'bold', fontSize: '12px', width: 170 },
  },
  {
    id: 'supervisor_validate',
    position: { x: 200, y: 100 },
    data: { label: 'Supervisor Agent\n(Validation & Routing)' },
    style: { background: '#F8FAFC', border: '2px solid #64748B', borderRadius: '12px', fontWeight: 'bold', fontSize: '12px', width: 170 },
  },
  {
    id: 'knowledge',
    position: { x: 380, y: 100 },
    data: { label: '📚 Knowledge Agent\n(RAG Citation & Runbooks)' },
    style: { background: '#ECFDF5', border: '2px solid #059669', borderRadius: '12px', fontWeight: 'bold', fontSize: '12px', width: 170 },
  },
  {
    id: 'diagnostic',
    position: { x: 560, y: 100 },
    data: { label: '🔬 Diagnostic Agent\n(MCP Tool Execution)' },
    style: { background: '#FAF5FF', border: '2px solid #7C3AED', borderRadius: '12px', fontWeight: 'bold', fontSize: '12px', width: 170 },
  },
  {
    id: 'resolution',
    position: { x: 740, y: 100 },
    data: { label: '⚖️ Resolution Agent\n(Synthesis & Approval Gate)' },
    style: { background: '#FFFBEB', border: '2px solid #D97706', borderRadius: '12px', fontWeight: 'bold', fontSize: '12px', width: 170 },
  },
  {
    id: 'ticket',
    position: { x: 920, y: 100 },
    data: { label: '🎫 Ticket Agent\n(USM Lifecycle via MCP)' },
    style: { background: '#F0FDF4', border: '2px solid #16A34A', borderRadius: '12px', fontWeight: 'bold', fontSize: '12px', width: 170 },
  },
];

const initialEdges: Edge[] = [
  { id: 'e1', source: 'triage', target: 'supervisor_validate', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e2', source: 'supervisor_validate', target: 'knowledge', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e3', source: 'knowledge', target: 'diagnostic', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e4', source: 'diagnostic', target: 'resolution', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e5', source: 'resolution', target: 'ticket', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
];

export const CommandCenterPage: React.FC<CommandCenterPageProps> = ({ onNavigate, currentUser }) => {
  const [runs, setRuns] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedRun, setSelectedRun] = useState<any>(null);
  const [runDetail, setRunDetail] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [engineers, setEngineers] = useState<EngineerAvailability[]>([]);
  const [engLoading, setEngLoading] = useState(false);

  // Workforce Continuity Policies (Checkpoint 5.1-E)
  const [policies, setPolicies] = useState<any[]>([]);
  const [policiesLoading, setPoliciesLoading] = useState(false);
  const [editPolicyModal, setEditPolicyModal] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<any | null>(null);
  const [policyWorkload, setPolicyWorkload] = useState(5);
  const [policyReassign, setPolicyReassign] = useState(3);
  const [policySLA, setPolicySLA] = useState(30);
  const [policyEscalate, setPolicyEscalate] = useState(true);
  const [policySkillMatch, setPolicySkillMatch] = useState(true);
  const [policySaving, setPolicySaving] = useState(false);
  const [policyError, setPolicyError] = useState('');
  const [policySuccess, setPolicySuccess] = useState<string | null>(null);

  // Global Continuity Exception Stream (Checkpoint 5.1-F)
  const [exceptions, setExceptions] = useState<AssignmentException[]>([]);
  const [excLoading, setExcLoading] = useState(false);
  const [excSearch, setExcSearch] = useState('');
  const [excFilter, setExcFilter] = useState('all');

  const fetchRuns = async () => {
    try {
      setLoading(true);
      setError('');
      const [runData, metricData] = await Promise.all([getAgentRuns(), getAgentRunMetrics()]);
      setRuns(runData);
      setMetrics(metricData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load agent execution history.');
    } finally {
      setLoading(false);
    }
  };

  const fetchEngineers = async () => {
    try {
      setEngLoading(true);
      setEngineers(await getWorkforceEngineers());
    } catch {
      /* non-critical */
    } finally {
      setEngLoading(false);
    }
  };

  const fetchPolicies = async () => {
    try {
      setPoliciesLoading(true);
      const data = await listAssignmentPolicies();
      setPolicies(data);
      setPolicyError(''); // clear any previous error on success
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load continuity policies.';
      setPolicyError(msg);
    } finally {
      setPoliciesLoading(false);
    }
  };

  const fetchExceptions = async () => {
    try {
      setExcLoading(true);
      const data = await listWorkforceExceptions({ limit: 50 });
      setExceptions(data);
    } catch {
      /* non-critical */
    } finally {
      setExcLoading(false);
    }
  };

  const handleOpenEditPolicy = (p: any) => {
    setEditingPolicy(p);
    setPolicyWorkload(p.max_workload_per_engineer ?? 5);
    setPolicyReassign(p.max_reassignment_attempts ?? 3);
    setPolicySLA(p.sla_at_risk_threshold_minutes ?? 30);
    setPolicyEscalate(p.auto_escalate_on_no_engineer ?? true);
    setPolicySkillMatch(p.require_skill_match ?? true);
    setPolicyError('');
    setEditPolicyModal(true);
  };

  const handleSavePolicy = async () => {
    if (!editingPolicy) return;
    if (policyWorkload < 1 || policyWorkload > 50) {
      setPolicyError('Max workload per engineer must be between 1 and 50.');
      return;
    }
    if (policyReassign < 1 || policyReassign > 10) {
      setPolicyError('Max reassignment attempts must be between 1 and 10.');
      return;
    }
    if (policySLA < 5 || policySLA > 360) {
      setPolicyError('SLA at-risk threshold must be between 5 and 360 minutes.');
      return;
    }
    if (!window.confirm(`Save changes to assignment policy '${editingPolicy.name}'?`)) return;

    try {
      setPolicySaving(true);
      setPolicyError('');
      await updateAssignmentPolicy(editingPolicy.name, {
        max_workload_per_engineer: policyWorkload,
        max_reassignment_attempts: policyReassign,
        sla_at_risk_threshold_minutes: policySLA,
        auto_escalate_on_no_engineer: policyEscalate,
        require_skill_match: policySkillMatch,
      });
      setPolicySuccess(`Policy '${editingPolicy.name}' updated successfully.`);
      setEditPolicyModal(false);
      await fetchPolicies();
    } catch (e) {
      setPolicyError(e instanceof Error ? e.message : 'Failed to update policy.');
    } finally {
      setPolicySaving(false);
    }
  };

  useEffect(() => {
    void fetchRuns();
    void fetchEngineers();
    void fetchPolicies();
    void fetchExceptions();
  }, []);

  const filteredExceptions = useMemo(() => {
    return exceptions.filter((exc) => {
      if (excFilter !== 'all' && exc.exception_type !== excFilter) return false;
      if (excSearch.trim()) {
        const q = excSearch.toLowerCase();
        const incMatch = `inc-${exc.incident_id}`.toLowerCase().includes(q) || String(exc.incident_id).includes(q);
        const reasonMatch = (exc.reason || '').toLowerCase().includes(q);
        const engMatch = (exc.attempted_engineer || '').toLowerCase().includes(q) || (exc.resolved_engineer || '').toLowerCase().includes(q);
        const typeMatch = exc.exception_type.toLowerCase().includes(q);
        return incMatch || reasonMatch || engMatch || typeMatch;
      }
      return true;
    });
  }, [exceptions, excFilter, excSearch]);

  const mostRecentRun = runs[0];
  const workflowNodes = useMemo(() => initialNodes.map((node) => {
    const agentName = node.id === 'supervisor_validate'
      ? 'Supervisor Agent'
      : `${node.id[0].toUpperCase()}${node.id.slice(1)} Agent`;
    const step = mostRecentRun?.steps?.filter((item: any) => item.step_name === agentName).slice(-1)[0];
    const status = step?.status;
    const border = status === 'failed' ? '#E11D48' : status === 'running' ? '#D97706' : status === 'waiting' ? '#7C3AED' : status === 'completed' ? '#059669' : '#CBD5E1';
    return {
      ...node,
      data: { ...node.data, label: `${node.data.label}${status ? `\n${status.toUpperCase()}` : ''}` },
      style: { ...node.style, border: `2px solid ${border}` },
    };
  }), [mostRecentRun]);

  const openRun = async (run: any) => {
    setSelectedRun(run);
    setRunDetail(null);
    setTimeline([]);
    setDetailError('');
    setDetailLoading(true);
    try {
      const [detail, events] = await Promise.all([
        getAgentRunDetail(run.run_id),
        run.incident_id ? getIncidentExecutionTimeline(run.incident_id) : Promise.resolve([]),
      ]);
      setRunDetail(detail);
      setTimeline(events);
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : 'Failed to load execution details.');
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-6 overflow-y-auto h-full bg-slate-50">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Agent Command Center</h2>
          <p className="text-xs text-slate-500 mt-1">
            Persisted LangGraph execution status, handoffs, tool activity, and decision summaries
          </p>
        </div>
        <div className="flex items-center gap-2">
          {onNavigate && (
            <button
              onClick={() => onNavigate('scenario-lab')}
              className="flex items-center space-x-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
            >
              <FlaskConical className="w-3.5 h-3.5" />
              <span>Scenario Testing Lab</span>
            </button>
          )}
          <button
            onClick={() => { void fetchRuns(); void fetchEngineers(); }}
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-sm transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh All</span>
          </button>
        </div>
      </div>

      {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[
          ['Total runs', metrics?.runs?.total],
          ['Running', metrics?.runs?.running],
          ['Waiting approval', metrics?.runs?.waiting],
          ['Completed', metrics?.runs?.completed],
          ['Failed', metrics?.runs?.failed],
        ].map(([label, value]) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{loading || !metrics ? '—' : value ?? 0}</p>
          </div>
        ))}
      </div>

      {/* Agent Performance */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <h3 className="text-sm font-bold text-slate-900 mb-3">Persisted agent performance</h3>
        {loading ? <p className="text-xs text-slate-500">Loading agent aggregates…</p> : !metrics ? (
          <p className="text-xs text-rose-700">Agent aggregates are unavailable.</p>
        ) : (metrics.agents || []).length === 0 ? (
          <p className="text-xs text-slate-500">No agent step executions have been recorded.</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {metrics.agents.map((agent: any) => (
              <div key={agent.agent} className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                <b className="text-slate-800">{agent.agent}</b>
                <p className="mt-1 text-slate-500">{agent.executions} executions · {agent.completed} completed · {agent.failed} failed</p>
                <p className="text-slate-500">Average: {agent.average_duration_ms == null ? '—' : `${agent.average_duration_ms} ms`}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Engineer Availability Panel */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Users className="w-4 h-4 text-violet-600" />
            Engineer Availability
          </h3>
          <button
            onClick={() => void fetchEngineers()}
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
        {engLoading ? (
          <p className="text-xs text-slate-500">Loading engineer availability…</p>
        ) : engineers.length === 0 ? (
          <p className="text-xs text-slate-500">No engineer availability records found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[640px]">
              <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Engineer</th>
                  <th className="px-3 py-2">Team</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Skills</th>
                  <th className="px-3 py-2">Workload</th>
                  <th className="px-3 py-2">Schedule</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {engineers.map((eng) => (
                  <tr key={eng.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <p className="font-semibold text-slate-800">{eng.full_name}</p>
                      <p className="text-[10px] text-slate-400">{eng.email}</p>
                    </td>
                    <td className="px-3 py-2 text-slate-600">{eng.team}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-col gap-1">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase w-fit ${
                          eng.availability_status === 'available' ? 'bg-emerald-100 text-emerald-700' :
                          eng.availability_status === 'on_leave' ? 'bg-amber-100 text-amber-700' :
                          eng.availability_status === 'busy' ? 'bg-orange-100 text-orange-700' :
                          'bg-slate-100 text-slate-600'
                        }`}>
                          {eng.availability_status.replace(/_/g, ' ')}
                        </span>
                        {eng.is_simulated && (
                          <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[9px] font-semibold text-violet-700 w-fit">Simulated</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {eng.skills.map((skill) => (
                          <span key={skill} className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700">{skill}</span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        <div className="h-1.5 w-16 rounded-full bg-slate-200 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${eng.current_workload >= eng.max_active_tickets ? 'bg-rose-500' : eng.current_workload >= eng.max_active_tickets * 0.7 ? 'bg-amber-400' : 'bg-emerald-500'}`}
                            style={{ width: `${Math.min(100, (eng.current_workload / (eng.max_active_tickets || 1)) * 100)}%` }}
                          />
                        </div>
                        <span className="text-slate-500">{eng.current_workload}/{eng.max_active_tickets}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-slate-500 text-[10px]">{eng.working_schedule || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Workforce Continuity Policies Panel (Checkpoint 5.1-E) */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-brand-blue" />
              Intelligent Assignment &amp; Continuity Policies
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Governs automated exception handling, workload caps, and skill-matching criteria
            </p>
          </div>
          <div className="flex items-center gap-2">
            {policySuccess && (
              <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
                {policySuccess}
              </span>
            )}
            {currentUser?.role === 'administrator' ? (
              <button
                type="button"
                onClick={() => handleOpenEditPolicy(policies[0] || { name: 'default' })}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-blue hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
              >
                <Sliders className="w-3.5 h-3.5" />
                Configure Policy
              </button>
            ) : (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-lg">
                <Shield className="w-3.5 h-3.5 text-slate-400" />
                Admin Governed
              </span>
            )}
          </div>
        </div>

        {policiesLoading ? (
          <p className="text-xs text-slate-500">Loading continuity policies…</p>
        ) : policies.length === 0 ? (
          <p className="text-xs text-slate-500">Default continuity policies active (5 tickets max, 3 attempts, skills enforced).</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {policies.map((p) => (
              <React.Fragment key={p.id || p.name}>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Max Workload / Engineer</span>
                  <p className="text-base font-bold text-slate-900">{p.max_workload_per_engineer ?? 5} <span className="text-xs font-normal text-slate-500">tickets</span></p>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Max Reassignment Tries</span>
                  <p className="text-base font-bold text-slate-900">{p.max_reassignment_attempts ?? 3} <span className="text-xs font-normal text-slate-500">attempts</span></p>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">SLA At-Risk Threshold</span>
                  <p className="text-base font-bold text-slate-900">{p.sla_at_risk_threshold_minutes ?? 30} <span className="text-xs font-normal text-slate-500">minutes</span></p>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Skill Matching</span>
                  <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase mt-1 ${p.require_skill_match ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}`}>
                    {p.require_skill_match ? 'Enforced' : 'Relaxed'}
                  </span>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Auto-Escalate Unassigned</span>
                  <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase mt-1 ${p.auto_escalate_on_no_engineer ? 'bg-amber-100 text-amber-800' : 'bg-slate-200 text-slate-700'}`}>
                    {p.auto_escalate_on_no_engineer ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </React.Fragment>
            ))}
          </div>
        )}
      </div>

      {/* React Flow Handoff Graph */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center">
          <Activity className="w-4 h-4 text-brand-blue mr-1.5" />
          LangGraph Workflow Map
        </h4>
        <div className="h-48 w-full border border-slate-100 rounded-lg bg-slate-50/50">
          <ReactFlow nodes={workflowNodes} edges={initialEdges} fitView attributionPosition="bottom-left">
            <Background gap={16} size={1} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      </div>

      {/* Execution Run History */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <h4 className="text-sm font-bold text-slate-900 mb-4 flex items-center">
          <Terminal className="w-4 h-4 mr-2 text-brand-blue" />
          Recent persisted LangGraph executions
        </h4>

        <div className="space-y-3">
          {loading ? (
            <p className="text-xs text-slate-500">Loading agent runs…</p>
          ) : error ? (
            <p className="text-xs text-rose-700">Execution history is unavailable.</p>
          ) : runs.length === 0 ? (
            <p className="text-xs text-slate-500">No agent runs recorded yet.</p>
          ) : (
            runs.map((r) => (
              <div key={r.run_id} className="border border-slate-200 rounded-lg p-3 bg-slate-50/60 text-xs">
                <div className="flex items-center justify-between font-semibold text-slate-800 mb-2">
                  <span className="font-mono text-brand-blue">Run #{r.run_id}: {r.agent_name} · {r.status} · retries {r.retry_count}</span>
                  <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
                    {r.incident_id ? (
                      <button
                        type="button"
                        onClick={() => onNavigate?.('incidents', r.incident_id)}
                        className="font-mono text-brand-blue font-bold hover:underline"
                        title="Open incident in queue"
                      >
                        INC-{String(r.incident_id).padStart(6, '0')}
                      </button>
                    ) : null}
                    <span>· Started: {r.started_at ? new Date(r.started_at).toLocaleString() : 'N/A'}</span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {r.steps.map((st: any, sIdx: number) => (
                    <span
                      key={st.step_id || sIdx}
                      className="inline-flex items-center space-x-1.5 px-2 py-1 rounded bg-white border border-slate-200 text-slate-700 font-medium"
                    >
                      {st.status === 'failed' ? <AlertCircle className="w-3 h-3 text-rose-500" /> : st.status === 'running' || st.status === 'waiting' ? <Clock3 className="w-3 h-3 text-amber-500" /> : <CheckCircle className="w-3 h-3 text-emerald-500" />}
                      <span>{st.step_name}</span>
                      <span className="font-mono text-slate-400 text-[10px]">({st.duration_ms == null ? st.status : `${st.duration_ms}ms`})</span>
                    </span>
                  ))}
                </div>
                <div className="mt-2 space-y-1">
                  {r.steps.map((st: any, sIdx: number) => (
                    <p key={`summary-${st.step_id || sIdx}`} className="text-[11px] text-slate-500">{st.step_name} · {st.status}: {st.summary || 'No decision summary recorded.'}</p>
                  ))}
                </div>
                <button onClick={() => void openRun(r)} className="mt-3 text-xs font-semibold text-brand-blue hover:underline">
                  Inspect execution
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Global Continuity Exception Stream (Checkpoint 5.1-F) */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-500" />
              Global Workforce Continuity Exception Stream
            </h4>
            <p className="text-xs text-slate-500 mt-0.5">
              Real-time audit stream of assignment failures, engineer unavailabilities, and continuity actions
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void fetchExceptions()}
              className="text-xs text-slate-600 hover:text-slate-900 flex items-center gap-1 border border-slate-200 px-2.5 py-1 rounded-lg hover:bg-slate-50 transition"
            >
              <RefreshCw className="w-3 h-3" /> Refresh Feed
            </button>
          </div>
        </div>

        {/* Search & Filter Controls */}
        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={excSearch}
              onChange={(e) => setExcSearch(e.target.value)}
              placeholder="Search by incident ID, engineer, reason..."
              className="w-full pl-8 pr-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-brand-blue"
            />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-slate-500 font-medium">Filter:</span>
            <select
              value={excFilter}
              onChange={(e) => setExcFilter(e.target.value)}
              className="border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue"
            >
              <option value="all">All Exceptions ({exceptions.length})</option>
              <option value="engineer_on_leave">Engineer On Leave</option>
              <option value="capacity_exceeded">Capacity Exceeded</option>
              <option value="no_eligible_engineer">No Eligible Engineer</option>
              <option value="concurrency_retry">Concurrency Retry</option>
              <option value="resolution_feedback">Resolution Feedback</option>
            </select>
          </div>
        </div>

        {/* Exception List */}
        {excLoading ? (
          <p className="text-xs text-slate-500">Loading continuity exceptions…</p>
        ) : filteredExceptions.length === 0 ? (
          <div className="text-center py-6 border border-dashed border-slate-200 rounded-lg">
            <CheckCircle className="w-6 h-6 text-emerald-500 mx-auto mb-1.5" />
            <p className="text-xs font-semibold text-slate-700">No continuity exceptions recorded</p>
            <p className="text-[11px] text-slate-400 mt-0.5">All automated workforce continuity and assignments are healthy.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[700px]">
              <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Timestamp</th>
                  <th className="px-3 py-2">Incident</th>
                  <th className="px-3 py-2">Exception Type</th>
                  <th className="px-3 py-2">Severity</th>
                  <th className="px-3 py-2">Attempted / Resolved</th>
                  <th className="px-3 py-2">Action Taken</th>
                  <th className="px-3 py-2">Safe Employee Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredExceptions.map((exc) => (
                  <tr key={exc.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2 text-slate-400 font-mono text-[10px] whitespace-nowrap">
                      {exc.created_at ? new Date(exc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                    </td>
                    <td className="px-3 py-2 font-mono font-bold">
                      {exc.incident_id ? (
                        <button
                          type="button"
                          onClick={() => onNavigate?.('incidents', exc.incident_id)}
                          className="text-brand-blue hover:underline"
                          title="Open incident in queue"
                        >
                          INC-{String(exc.incident_id).padStart(6, '0')}
                        </button>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-medium text-slate-800">
                      <span className="capitalize">{exc.exception_type.replace(/_/g, ' ')}</span>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                        exc.severity === 'critical' ? 'bg-rose-100 text-rose-700' :
                        exc.severity === 'warning' ? 'bg-amber-100 text-amber-700' :
                        'bg-blue-100 text-blue-700'
                      }`}>
                        {exc.severity}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-600 text-[11px]">
                      <div><span className="text-slate-400">Att:</span> {exc.attempted_engineer || 'None'}</div>
                      {exc.resolved_engineer && <div><span className="text-slate-400">Res:</span> <span className="font-semibold text-emerald-700">{exc.resolved_engineer}</span></div>}
                    </td>
                    <td className="px-3 py-2 text-slate-600 max-w-[200px] truncate" title={exc.action_taken || exc.reason || undefined}>
                      {exc.action_taken || exc.reason || '—'}
                    </td>
                    <td className="px-3 py-2 text-slate-500 italic max-w-[220px] truncate" title={exc.employee_message || ''}>
                      "{exc.employee_message || 'Assigned to qualified specialist.'}"
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedRun && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Agent execution details">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto p-5 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-bold text-slate-900">Execution #{selectedRun.run_id}</h3>
                <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                  <span>Incident {selectedRun.incident_id ? `INC-${String(selectedRun.incident_id).padStart(6, '0')}` : 'not linked'} · {selectedRun.status}</span>
                  {selectedRun.incident_id && onNavigate && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedRun(null);
                        onNavigate('incidents', selectedRun.incident_id);
                      }}
                      className="text-xs font-semibold text-brand-blue hover:underline inline-flex items-center gap-0.5"
                    >
                      <ExternalLink className="w-3 h-3" /> Open in Incident Queue
                    </button>
                  )}
                </div>
              </div>
              <button onClick={() => setSelectedRun(null)} aria-label="Close execution details"><X className="w-5 h-5 text-slate-500" /></button>
            </div>
            {detailError && <p role="alert" className="text-sm text-rose-700">{detailError}</p>}
            {detailLoading ? <p className="text-sm text-slate-500">Loading persisted execution detail…</p> : runDetail && (
              <>
                <section className="grid sm:grid-cols-2 gap-3 text-sm">
                  <div className="rounded-lg bg-slate-50 p-3"><b>Input summary</b><p className="mt-1 whitespace-pre-wrap text-slate-600">{runDetail.input_summary || 'Not recorded'}</p></div>
                  <div className="rounded-lg bg-slate-50 p-3"><b>Output summary</b><p className="mt-1 whitespace-pre-wrap text-slate-600">{runDetail.output_summary || 'Not recorded'}</p></div>
                </section>
                <p className="text-xs text-slate-500">Token usage and model identity are not captured by the current execution records.</p>
                <section>
                  <h4 className="text-sm font-bold mb-2">Retrieved knowledge references</h4>
                  {(runDetail.execution?.retrieved_knowledge || []).length ? (runDetail.execution.retrieved_knowledge.map((item: any, idx: number) => (
                    <div key={idx} className="border rounded-lg p-3 mb-2 text-xs">
                      <b>{item.document || 'Knowledge document'}</b> · {item.citation || 'No citation'}
                      <p className="text-slate-500 mt-1">Score: {item.score == null ? 'Unavailable for zero-vector embeddings' : `${item.score} (${item.score_method})`}</p>
                    </div>
                  ))) : <p className="text-xs text-slate-500">No retrieved knowledge references recorded.</p>}
                </section>
                <section>
                  <h4 className="text-sm font-bold mb-2">MCP tool calls</h4>
                  {(runDetail.tool_invocations || []).length ? runDetail.tool_invocations.map((call: any) => (
                    <div key={call.call_id} className="border rounded-lg p-3 mb-2 text-xs">
                      <b>{call.tool}</b> · {call.agent || 'Unattributed'} · {call.status} · {call.duration_ms ?? '—'} ms
                      <p className="text-slate-500 mt-1 break-words">{call.output_summary || 'No output summary'}</p>
                    </div>
                  )) : <p className="text-xs text-slate-500">No tool calls are linked to this run.</p>}
                </section>
                {runDetail.error_summary && <p className="rounded-lg bg-rose-50 p-3 text-xs text-rose-800">Failure: {runDetail.error_summary}</p>}
                {timeline.length > 0 && (
                  <section>
                    <h4 className="text-sm font-bold mb-2">Incident execution timeline</h4>
                    <ol className="space-y-2">
                      {timeline.map((event) => (
                        <li key={event.event_id} className="text-xs border-l-2 border-brand-blue pl-3 py-1">
                          <b>{event.event_type}</b> · {event.status || 'recorded'} · {event.timestamp ? new Date(event.timestamp).toLocaleString() : 'time unavailable'}
                          <p className="text-slate-500">{event.summary || ''}</p>
                        </li>
                      ))}
                    </ol>
                  </section>
                )}
              </>
            )}
          </div>
        </div>
      )}
      {/* Policy Edit Modal (Checkpoint 5.1-E) */}
      {editPolicyModal && editingPolicy && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="policy-modal-title">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Sliders className="w-5 h-5 text-brand-blue" />
                <h3 id="policy-modal-title" className="font-bold text-slate-900 text-base">
                  Configure Continuity Policy: {editingPolicy.name}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setEditPolicyModal(false)}
                className="text-slate-400 hover:text-slate-600"
                aria-label="Close policy modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {policyError && (
              <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-700 flex items-center gap-2" role="alert">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{policyError}</span>
              </div>
            )}

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Max Active Workload per Engineer (1 - 50)
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={policyWorkload}
                  onChange={(e) => setPolicyWorkload(parseInt(e.target.value) || 1)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-blue"
                />
                <p className="text-[11px] text-slate-400 mt-0.5">Tickets assigned above this cap trigger automated load balancing.</p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Max Reassignment Attempts (1 - 10)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={policyReassign}
                  onChange={(e) => setPolicyReassign(parseInt(e.target.value) || 1)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-blue"
                />
                <p className="text-[11px] text-slate-400 mt-0.5">Maximum fallback iterations before escalating to team lead/supervisor.</p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  SLA At-Risk Threshold (5 - 360 minutes)
                </label>
                <input
                  type="number"
                  min={5}
                  max={360}
                  value={policySLA}
                  onChange={(e) => setPolicySLA(parseInt(e.target.value) || 5)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-blue"
                />
                <p className="text-[11px] text-slate-400 mt-0.5">Remaining resolution time when incident is flagged 'at risk'.</p>
              </div>

              <div className="pt-2 space-y-2 border-t border-slate-100">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={policySkillMatch}
                    onChange={(e) => setPolicySkillMatch(e.target.checked)}
                    className="rounded border-slate-300 text-brand-blue focus:ring-brand-blue h-4 w-4"
                  />
                  <span className="font-semibold text-slate-700">Enforce Strict Skill Matching</span>
                </label>
                <p className="text-[11px] text-slate-400 ml-6">Requires assigned engineer to possess classified skills for category.</p>

                <label className="flex items-center gap-2 cursor-pointer pt-1">
                  <input
                    type="checkbox"
                    checked={policyEscalate}
                    onChange={(e) => setPolicyEscalate(e.target.checked)}
                    className="rounded border-slate-300 text-brand-blue focus:ring-brand-blue h-4 w-4"
                  />
                  <span className="font-semibold text-slate-700">Auto-Escalate if No Eligible Engineer</span>
                </label>
                <p className="text-[11px] text-slate-400 ml-6">Immediately flags incident as escalated when all engineers are unavailable or at capacity.</p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setEditPolicyModal(false)}
                className="px-3.5 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition"
                disabled={policySaving}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSavePolicy}
                disabled={policySaving}
                className="px-3.5 py-1.5 rounded-lg bg-brand-blue text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50 transition shadow-sm"
              >
                {policySaving ? 'Saving Changes…' : 'Save Policy Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
