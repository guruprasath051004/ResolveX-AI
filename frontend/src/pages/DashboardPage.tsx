import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Cpu,
  Layers,
  ShieldCheck,
  TrendingUp,
  FileCheck2,
  RefreshCw,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from 'recharts';
import {
  DashboardStats,
  getDashboardStats,
  getOperationalInsights,
  OperationalInsight,
  User,
} from '../services/api';

interface DashboardPageProps {
  currentUser: User;
  onNavigate?: (page: string, incidentId?: number) => void;
}

function utcDateString(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ currentUser, onNavigate }) => {
  const today = new Date();
  const [startDate, setStartDate] = useState(
    utcDateString(new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - 29))),
  );
  const [endDate, setEndDate] = useState(utcDateString(today));
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [insights, setInsights] = useState<OperationalInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchStats = async (from = startDate, to = endDate) => {
    try {
      setLoading(true);
      setError('');
      if (currentUser.role === 'administrator') {
        const [data, signals] = await Promise.all([
          getDashboardStats(from, to),
          getOperationalInsights(from, to),
        ]);
        setStats(data);
        setInsights(signals?.insights || (Array.isArray(signals) ? signals : []));
      } else {
        setStats(await getDashboardStats());
        setInsights([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load dashboard metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const COLORS = ['#2563EB', '#7C3AED', '#06B6D4', '#F59E0B', '#EF4444'];

  if (loading && !stats) {
    return (
      <div className="p-8 text-center text-slate-500 text-sm">
        Loading real-time USM dashboard aggregates...
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="space-y-3 p-8">
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
        <button
          onClick={() => fetchStats()}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700"
        >
          Retry dashboard
        </button>
      </div>
    );
  }

  if (currentUser.role === 'support_engineer') {
    return (
      <div className="p-8 space-y-8 overflow-y-auto h-full bg-slate-50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Support Operations Dashboard</h2>
            <p className="text-xs text-slate-500 mt-1">
              Live work queue and service health for the Support Engineer role
            </p>
          </div>
          <button
            onClick={() => fetchStats()}
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-sm transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Queue</span>
          </button>
        </div>

        {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <MetricCard label="Assigned to me" value={stats?.assigned_incidents ?? 0} tone="blue" />
          <MetricCard label="Open Incidents" value={stats?.open_incidents ?? 0} tone="amber" />
          <MetricCard label="Unassigned" value={stats?.unassigned_incidents ?? 0} tone="blue" />
          <MetricCard label="In Progress" value={stats?.in_progress_incidents ?? 0} tone="amber" />
          <MetricCard label="Critical Incidents" value={stats?.critical_incidents ?? 0} tone="rose" />
          <MetricCard label="Approaching SLA" value={stats?.approaching_sla_count ?? 0} tone="rose" />
          <MetricCard label="Pending Approvals" value={stats?.pending_approvals_count ?? 0} tone="blue" />
          <MetricCard label="Resolved Incidents" value={stats?.resolved_incidents ?? 0} tone="green" />
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 mb-4">Team workload</h3>
            {stats?.team_workload?.length ? (
              <div className="space-y-3">
                {stats.team_workload.map((team: any) => (
                  <div key={team.team} className="flex items-center justify-between border-b border-slate-100 pb-2 text-sm">
                    <span className="text-slate-700">{team.team}</span>
                    <span className="font-bold text-slate-900">{team.active_incidents}</span>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-slate-500">No active incidents are assigned to a team.</p>}
          </section>
          <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 mb-4">Recent agent executions</h3>
            {stats?.recent_agent_runs?.length ? (
              <div className="space-y-3">
                {stats.recent_agent_runs.map((run: any) => (
                  <div key={run.id} className="border-l-2 border-brand-blue pl-3 py-1">
                    <p className="text-sm font-semibold text-slate-800">{run.agent_name} · {run.status}</p>
                    <p className="text-xs text-slate-500">
                      {run.incident_id ? (
                        <button
                          type="button"
                          onClick={() => onNavigate?.('incidents', run.incident_id)}
                          className="font-mono text-brand-blue hover:underline font-bold mr-1"
                        >
                          INC-{String(run.incident_id).padStart(6, '0')}
                        </button>
                      ) : null}
                      {run.started_at ? new Date(run.started_at).toLocaleString() : 'Start time unavailable'}
                    </p>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-slate-500">No agent runs have been recorded.</p>}
          </section>
          <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm lg:col-span-2">
            <h3 className="text-sm font-bold text-slate-800 mb-4">Recent diagnostic activity</h3>
            {stats?.activity_timeline?.length ? (
              <div className="space-y-3">
                {stats.activity_timeline.map((activity: any) => (
                  <div key={activity.id} className="border-l-2 border-brand-blue pl-3 py-1">
                    <p className="text-sm font-semibold text-slate-800">{activity.action} · {activity.status}</p>
                    <p className="text-xs text-slate-500">{activity.summary || 'No output summary was recorded.'} {activity.time ? `· ${new Date(activity.time).toLocaleString()}` : ''}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No diagnostic activity has been recorded yet.</p>
            )}
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 overflow-y-auto h-full bg-slate-50">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Administrator Dashboard</h2>
          <p className="text-xs text-slate-500 mt-1">
            Database-backed incident and SLA metrics for the selected date range
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-[11px] font-medium text-slate-600">
            From (UTC)
            <input
              aria-label="Dashboard start date"
              type="date"
              value={startDate}
              max={endDate}
              onChange={(event) => setStartDate(event.target.value)}
              className="mt-1 block rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700"
            />
          </label>
          <label className="text-[11px] font-medium text-slate-600">
            To (UTC)
            <input
              aria-label="Dashboard end date"
              type="date"
              value={endDate}
              min={startDate}
              max={utcDateString(new Date())}
              onChange={(event) => setEndDate(event.target.value)}
              className="mt-1 block rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700"
            />
          </label>
          <button
            onClick={() => fetchStats()}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 disabled:opacity-60 text-slate-700 rounded-lg text-xs font-semibold shadow-sm transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Refreshing…' : 'Apply / Refresh'}</span>
          </button>
        </div>
      </div>

      {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      {/* SLA Breach Alerts Banner */}
      {stats && (stats.sla_breaches?.length ?? 0) > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center font-bold shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-rose-900">
                SLA Breach Warning: {stats.sla_breaches[0].title}
              </h4>
              <p className="text-xs text-rose-700">
                Severity: {stats.sla_breaches[0].severity} | {stats.sla_breaches[0].status}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold px-3 py-1 bg-rose-600 text-white rounded-lg shadow-sm">
              {stats.sla_breaches[0].time_remaining_min < 0
                ? `Breached by ${Math.abs(stats.sla_breaches[0].time_remaining_min)}m`
                : `${stats.sla_breaches[0].time_remaining_min}m to deadline`}
            </span>
            {stats.sla_breaches[0].id && onNavigate && (
              <button
                type="button"
                onClick={() => onNavigate('incidents', stats.sla_breaches[0].id)}
                className="px-3 py-1 bg-white border border-rose-300 hover:bg-rose-100 text-rose-800 text-xs font-semibold rounded-lg transition"
              >
                Inspect Incident →
              </button>
            )}
          </div>
        </div>
      )}

      {/* Primary incident metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {/* Total Incidents */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Incidents</span>
            <Layers className="w-4 h-4 text-brand-blue" />
          </div>
          <p className="text-3xl font-extrabold text-slate-900">{stats?.total_incidents ?? 0}</p>
          <span className="text-[11px] text-slate-400 mt-1 block">Live DB Rows</span>
        </div>

        {/* Open Incidents */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Open Incidents</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-3xl font-extrabold text-amber-600">{stats?.open_incidents ?? 0}</p>
          <span className="text-[11px] text-slate-400 mt-1 block">Open or assigned</span>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">In Progress</span>
            <Clock className="w-4 h-4 text-blue-500" />
          </div>
          <p className="text-3xl font-extrabold text-blue-600">{stats?.in_progress_incidents ?? 0}</p>
          <span className="text-[11px] text-slate-400 mt-1 block">Investigating or in progress</span>
        </div>

        {/* Resolved */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Resolved Tickets</span>
            <CheckCircle className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-3xl font-extrabold text-emerald-600">{stats?.resolved_incidents ?? 0}</p>
          <span className="text-[11px] text-slate-400 mt-1 block">Completed Workflows</span>
        </div>

        {/* Critical Incidents */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Critical P1</span>
            <AlertTriangle className="w-4 h-4 text-rose-500" />
          </div>
          <p className="text-3xl font-extrabold text-rose-600">{stats?.critical_incidents ?? 0}</p>
          <span className="text-[11px] text-rose-500 font-semibold mt-1 block">High Impact Tier</span>
        </div>
      </div>

      {/* Secondary Efficiency & Operational KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* SLA Compliance % */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">SLA Milestone Compliance</span>
            <span className="text-xl font-bold text-slate-900">{stats?.sla_compliance_pct == null ? 'No data' : `${stats.sla_compliance_pct}%`}</span>
            <span className="text-[10px] text-slate-400">{stats?.sla_compliance_sample_count ?? 0} recorded milestones</span>
          </div>
        </div>

        {/* AI Automation Rate */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 text-brand-blue flex items-center justify-center font-bold shrink-0">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Agent-linked resolution</span>
            <span className="text-xl font-bold text-slate-900">{stats?.ai_automation_rate_pct == null ? 'No data' : `${stats.ai_automation_rate_pct}%`}</span>
            <span className="text-[10px] text-slate-400">{stats?.ai_automation_sample_count ?? 0} resolved incidents sampled</span>
          </div>
        </div>

        {/* Average Resolution Time */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-purple-50 text-brand-violet flex items-center justify-center font-bold shrink-0">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Avg Resolution</span>
            <span className="text-xl font-bold text-slate-900">{stats?.average_resolution_time_min == null ? 'No data' : `${stats.average_resolution_time_min}m`}</span>
          </div>
        </div>

        {/* Pending Approvals */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center font-bold shrink-0">
            <FileCheck2 className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Pending Approvals</span>
            <span className="text-xl font-bold text-amber-600">{stats?.pending_approvals_count ?? 0}</span>
          </div>
        </div>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Operational insights</h3>
            <p className="mt-1 text-xs text-slate-500">
              Explainable signals from incident, workload, asset and SLA records; not generated predictions.
            </p>
          </div>
          <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-semibold text-blue-700">
            DATABASE RULES
          </span>
        </div>
        {(insights?.length ?? 0) > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {insights.map((insight) => (
              <article key={insight.key} className="rounded-lg border border-slate-100 bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-sm font-semibold text-slate-800">{insight.title}</h4>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                    insight.severity === 'critical'
                      ? 'bg-rose-100 text-rose-700'
                      : insight.severity === 'warning'
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-slate-200 text-slate-700'
                  }`}>
                    {insight.severity}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-600">{insight.explanation}</p>
                <p className="mt-2 text-xs leading-5 text-slate-700">
                  <strong>Suggested review:</strong> {insight.recommendation}
                </p>
              </article>
            ))}
          </div>
        ) : (
          <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">
            No operational signals crossed the displayed evidence thresholds for this date range.
          </p>
        )}
      </section>

      {/* Visual Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trend Area Chart */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h4 className="text-sm font-bold text-slate-800 mb-4">Incidents Created and Resolved</h4>
          <div className="h-64">
            {!stats?.trend_chart?.length ? <div className="flex h-full items-center justify-center text-sm text-slate-400">No incident trend data for this period.</div> : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats?.trend_chart || []}>
                <defs>
                  <linearGradient id="incColor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563EB" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#2563EB" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#94A3B8" fontSize={11} />
                <YAxis stroke="#94A3B8" fontSize={11} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="incidents" stroke="#2563EB" strokeWidth={2} fillOpacity={1} fill="url(#incColor)" />
                <Area type="monotone" dataKey="resolved" name="Resolved" stroke="#059669" strokeWidth={2} fill="transparent" />
              </AreaChart>
            </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Priority Breakdown (Pie) */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <h4 className="text-sm font-bold text-slate-800 mb-2">Priority Distribution (SQL Group By)</h4>
          <div className="h-48">
            {!stats?.priority_distribution?.length ? <div className="flex h-full items-center justify-center text-xs text-slate-400">No incident data.</div> : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={stats?.priority_distribution || []}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={70}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {(stats?.priority_distribution || []).map((_: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 mt-2">
            {(stats?.priority_distribution || []).map((p: any, idx: number) => (
              <div key={idx} className="flex items-center space-x-2 text-xs text-slate-600">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                <span>{p.name}: {p.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Activity Timeline & Category Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Category Breakdown (Bar) */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h4 className="text-sm font-bold text-slate-800 mb-4">Category Breakdown</h4>
          <div className="h-60">
            {!stats?.category_breakdown?.length ? <div className="flex h-full items-center justify-center text-xs text-slate-400">No incident data.</div> : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats?.category_breakdown || []}>
                <XAxis dataKey="name" stroke="#94A3B8" fontSize={11} />
                <YAxis stroke="#94A3B8" fontSize={11} />
                <Tooltip />
                <Bar dataKey="value" fill="#7C3AED" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h4 className="text-sm font-bold text-slate-800 mb-4">Status Distribution</h4>
          <div className="h-60">
            {!stats?.status_distribution?.length ? <div className="flex h-full items-center justify-center text-xs text-slate-400">No incident data.</div> : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.status_distribution}>
                <XAxis dataKey="name" stroke="#94A3B8" fontSize={10} interval={0} angle={-15} textAnchor="end" height={55} />
                <YAxis stroke="#94A3B8" fontSize={11} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" fill="#0891B2" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Real-time Activity Timeline */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col">
          <h4 className="text-sm font-bold text-slate-800 mb-4">Recent Agent & MCP Activity Timeline</h4>
          <div className="space-y-3 flex-1 overflow-y-auto max-h-60">
            {stats?.activity_timeline?.length ? stats.activity_timeline.map((act: any) => (
              <div key={act.id} className="text-xs border-l-2 border-brand-blue pl-3 py-1 space-y-0.5">
                <div className="flex items-center justify-between font-semibold text-slate-800">
                  <span>{act.action}</span>
                  <span className="text-[10px] text-slate-400 font-mono">{act.duration_ms}ms</span>
                </div>
                <p className="text-slate-500 text-[11px] line-clamp-1">{act.summary}</p>
              </div>
            )) : <p className="text-sm text-slate-500">No agent or MCP activity recorded.</p>}
          </div>
        </div>
      </div>
    </div>
  );
};

interface MetricCardProps {
  label: string;
  value: number;
  tone: 'amber' | 'rose' | 'blue' | 'green';
}

const TONE_CLASSES: Record<MetricCardProps['tone'], string> = {
  amber: 'text-amber-600',
  rose: 'text-rose-600',
  blue: 'text-brand-blue',
  green: 'text-emerald-600',
};

const MetricCard: React.FC<MetricCardProps> = ({ label, value, tone }) => (
  <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
    <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
    <p className={`mt-2 text-3xl font-extrabold ${TONE_CLASSES[tone]}`}>{value}</p>
    <span className="text-[11px] text-slate-400 mt-1 block">Live DB Rows</span>
  </div>
);

