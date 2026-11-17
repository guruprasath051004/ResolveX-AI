import React, { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, ShieldCheck } from 'lucide-react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  getSLABreaches,
  getSLAPolicies,
  getSLATrends,
  SLAPolicy,
  SLARisk,
  SLATrendPoint,
} from '../services/api';

function utcDateString(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export const SLAPage: React.FC = () => {
  const today = new Date();
  const [startDate, setStartDate] = useState(
    utcDateString(new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - 29))),
  );
  const [endDate, setEndDate] = useState(utcDateString(today));
  const [policies, setPolicies] = useState<SLAPolicy[]>([]);
  const [trends, setTrends] = useState<SLATrendPoint[]>([]);
  const [breaches, setBreaches] = useState<SLARisk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchSlaData = async (from = startDate, to = endDate) => {
    try {
      setLoading(true);
      setError('');
      const [policyData, riskData, trendData] = await Promise.all([
        getSLAPolicies(from, to),
        getSLABreaches({ windowMinutes: 60 }),
        getSLATrends(from, to),
      ]);
      setPolicies(policyData);
      setBreaches(riskData);
      setTrends(trendData.trend);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load SLA information.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSlaData();
  }, []);

  const breachedCount = breaches.filter((item) => item.risk === 'breached').length;
  const atRiskCount = breaches.filter((item) => item.risk === 'at_risk').length;
  const hasTrendSamples = trends.some(
    (item) => item.response_sample_count > 0 || item.resolution_sample_count > 0,
  );

  return (
    <div className="h-full overflow-y-auto bg-slate-50 p-8">
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">SLA Policies & Compliance</h2>
            <p className="mt-1 text-xs text-slate-500">
              Policy targets are unchanged; performance is calculated from recorded incident deadlines and outcomes.
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-[11px] font-medium text-slate-600">
              From (UTC)
              <input
                aria-label="SLA start date"
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
                aria-label="SLA end date"
                type="date"
                value={endDate}
                min={startDate}
                max={utcDateString(new Date())}
                onChange={(event) => setEndDate(event.target.value)}
                className="mt-1 block rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700"
              />
            </label>
            <button
              onClick={() => fetchSlaData()}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-60"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Refreshing…' : 'Apply / Refresh'}
            </button>
          </div>
        </div>

        {error && (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            {error}
          </p>
        )}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {loading && policies.length === 0 ? (
            <p className="text-sm text-slate-500">Loading configured SLA policies…</p>
          ) : error && policies.length === 0 ? (
            <p className="text-sm text-slate-500">SLA policy data is unavailable until the request succeeds.</p>
          ) : policies.length === 0 ? (
            <p className="text-sm text-slate-500">No SLA policies are configured.</p>
          ) : (
            policies.map((policy) => (
              <article key={policy.id} className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div>
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <h3 className="text-sm font-bold text-slate-900">{policy.name}</h3>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                      policy.status === 'Compliant'
                        ? 'bg-emerald-100 text-emerald-700'
                        : policy.status === 'At Risk'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-slate-100 text-slate-600'
                    }`}>
                      {policy.status}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
                    <div className="rounded bg-slate-50 p-2">
                      <span className="block text-[10px] uppercase text-slate-400">Response target</span>
                      <strong className="text-slate-800">{policy.response_minutes} min</strong>
                    </div>
                    <div className="rounded bg-slate-50 p-2">
                      <span className="block text-[10px] uppercase text-slate-400">Resolution target</span>
                      <strong className="text-slate-800">{policy.resolution_minutes} min</strong>
                    </div>
                  </div>
                </div>
                <div className="mt-4 space-y-2 border-t border-slate-100 pt-3 text-xs">
                  <div className="flex justify-between gap-2">
                    <span className="text-slate-500">Response compliance</span>
                    <strong className="text-slate-800">
                      {policy.response_compliance_pct == null ? 'No data' : `${policy.response_compliance_pct}%`}
                      <span className="ml-1 font-normal text-slate-400">({policy.response_sample_count})</span>
                    </strong>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-slate-500">Resolution compliance</span>
                    <strong className="text-slate-800">
                      {policy.resolution_compliance_pct == null ? 'No data' : `${policy.resolution_compliance_pct}%`}
                      <span className="ml-1 font-normal text-slate-400">({policy.resolution_sample_count})</span>
                    </strong>
                  </div>
                  <div className="flex justify-between gap-2 border-t border-slate-100 pt-2">
                    <span className="font-semibold text-slate-600">Combined milestone rate</span>
                    <strong className="text-brand-blue">
                      {policy.compliance_rate_pct == null ? 'No data' : `${policy.compliance_rate_pct}%`}
                    </strong>
                  </div>
                </div>
              </article>
            ))
          )}
        </div>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-brand-blue" />
              <h3 className="text-sm font-bold text-slate-900">Historical SLA compliance</h3>
            </div>
            <span className="text-[11px] text-slate-500">Resolved incident outcomes, grouped by UTC resolution date</span>
          </div>
          <div className="h-72">
            {!hasTrendSamples ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-500">
                No response or resolution SLA outcomes were recorded in this date range.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="date" stroke="#94A3B8" fontSize={10} minTickGap={24} />
                  <YAxis domain={[0, 100]} unit="%" stroke="#94A3B8" fontSize={11} />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="response_compliance_pct"
                    name="Response"
                    stroke="#2563EB"
                    strokeWidth={2}
                    connectNulls
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="resolution_compliance_pct"
                    name="Resolution"
                    stroke="#7C3AED"
                    strokeWidth={2}
                    connectNulls
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <h3 className="text-sm font-bold text-slate-900">Active SLA risks</h3>
            </div>
            <div className="flex gap-2 text-[10px] font-bold uppercase">
              <span className="rounded-full bg-rose-100 px-2 py-1 text-rose-700">Breached {breachedCount}</span>
              <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-700">At risk {atRiskCount}</span>
            </div>
          </div>
          <p className="mb-4 text-xs text-slate-500">
            Active incidents with a missed response/resolution deadline or a deadline within 60 minutes.
            Escalation eligibility is informational; this view does not execute escalations.
          </p>
          {loading && breaches.length === 0 ? (
            <p className="text-sm text-slate-500">Checking active deadlines…</p>
          ) : breaches.length === 0 ? (
            <p className="text-sm text-slate-500">No active incidents are breached or due within the next hour.</p>
          ) : (
            <div className="space-y-2">
              {breaches.map((item) => (
                <article key={item.incident_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-100 p-3">
                  <div>
                    <strong className="text-xs text-slate-900">{item.ticket_id}</strong>
                    <span className="ml-2 text-xs uppercase text-slate-500">
                      {item.priority_code ?? item.priority} · {item.status}
                    </span>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Response: {item.response_risk ?? 'on track'} · Resolution: {item.resolution_risk ?? 'on track'}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs font-semibold ${item.risk === 'breached' ? 'text-rose-700' : 'text-amber-700'}`}>
                      {item.risk === 'breached'
                        ? `Breached by ${Math.abs(item.minutes_remaining)}m`
                        : `${item.minutes_remaining}m to ${item.deadline_type} deadline`}
                    </span>
                    {item.escalation_eligible && (
                      <p className="mt-1 text-[10px] font-medium text-rose-600">Eligible for policy review</p>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
