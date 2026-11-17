import React, { useCallback, useEffect, useState } from 'react';
import { Layers, Activity, RefreshCw } from 'lucide-react';
import { getMCPCalls, getMCPMetrics, getMCPStatus } from '../services/api';

export const MCPMonitorPage: React.FC = () => {
  const [status, setStatus] = useState<any>(null);
  const [calls, setCalls] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async (searchValue = search, statusValue = statusFilter) => {
    try {
      setLoading(true);
      setError('');
      const [sData, cData, metricData] = await Promise.all([
        getMCPStatus(),
        getMCPCalls({ search: searchValue, status: statusValue }),
        getMCPMetrics(),
      ]);
      setStatus(sData);
      setCalls(cData);
      setMetrics(metricData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load MCP status and audit records.');
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    const timer = window.setTimeout(() => fetchData(search, statusFilter), 250);
    return () => window.clearTimeout(timer);
  }, [fetchData, search, statusFilter]);

  return (
    <div className="p-8 space-y-6 overflow-y-auto h-full bg-slate-50">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">MCP Server Monitor</h2>
          <p className="text-xs text-slate-500 mt-1">
            Actual in-process MCP registry and persisted tool audit records; remote HTTP transport is not used by this client
          </p>
        </div>
        <button
          onClick={() => fetchData()}
          className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-sm transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      {/* Server Status Header Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Server Status</span>
          <div className="flex items-center space-x-2 mt-1">
            <span className={`w-2.5 h-2.5 rounded-full ${status?.status === 'available' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="text-lg font-bold text-slate-900 uppercase">{status?.status || (loading ? 'CHECKING' : 'UNKNOWN')}</span>
          </div>
          <span className="text-[10px] text-slate-400 block mt-1">{status?.transport || 'Transport unavailable'} · remote used: {status?.remote_server_used ? 'yes' : 'no'}</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Registered Tools</span>
          <span className="text-2xl font-extrabold text-brand-blue block mt-1">{status?.total_tools ?? '—'}</span>
          <span className="text-[10px] text-slate-400 block mt-1">JSON-Schema Validated</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Recent Calls</span>
          <span className="text-2xl font-extrabold text-brand-violet block mt-1">{metrics?.calls?.total ?? '—'}</span>
          <span className="text-[10px] text-slate-400 block mt-1">All persisted invocations</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Audit Scope</span>
          <span className="text-xs font-bold text-slate-700 block mt-2">Successful {metrics?.calls?.successful ?? '—'} · Failed {metrics?.calls?.failed ?? '—'}</span>
          <span className="text-[10px] text-slate-400 block mt-1">Authorization failures {metrics?.calls?.authorization_failures ?? '—'} · Timeouts {metrics?.calls?.timeouts ?? '—'}</span>
          <span className="text-[10px] text-amber-700 block mt-1">Authentication failures are not recorded in MCP call rows.</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="bg-white p-4 rounded-xl border border-slate-200"><span className="text-[11px] text-slate-500">Average latency</span><p className="text-xl font-bold">{metrics?.calls?.average_latency_ms == null ? '—' : `${metrics.calls.average_latency_ms} ms`}</p></div>
        <div className="bg-white p-4 rounded-xl border border-slate-200"><span className="text-[11px] text-slate-500">Registered tools</span><p className="text-xl font-bold">{status?.total_tools ?? '—'}</p></div>
        <div className="bg-white p-4 rounded-xl border border-slate-200"><span className="text-[11px] text-slate-500">Integration mode</span><p className="text-xl font-bold">In-process</p></div>
      </div>

      {/* Registered Tools Grid */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <h4 className="text-sm font-bold text-slate-900 mb-4 flex items-center">
          <Layers className="w-4 h-4 mr-2 text-brand-blue" />
          Registered MCP Tools
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {status?.tools?.map((tool: any, idx: number) => (
            <div key={idx} className="p-3 rounded-lg border border-slate-100 bg-slate-50 text-xs">
              <span className="font-mono font-bold text-brand-blue">{tool.name}</span>
              <span className={`ml-2 inline-flex rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${tool.integration_mode === 'simulated' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>{tool.integration_mode?.replace('_', ' ')}</span>
              <p className="text-slate-600 text-[11px] mt-1">{tool.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Tool Call History Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <h4 className="text-sm font-bold text-slate-900 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-brand-violet" />
            Searchable execution audit log
          </h4>
          <div className="flex items-center gap-2">
            <input aria-label="Search MCP calls" className="border rounded-lg px-3 py-1.5 text-xs" placeholder="Search calls…" value={search} onChange={(event) => setSearch(event.target.value)} />
            <select aria-label="Filter MCP call status" className="border rounded-lg px-2 py-1.5 text-xs" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All statuses</option><option value="success">Success</option><option value="error">Failed</option>
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 border-b border-slate-200 font-semibold uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4">Call #</th>
                <th className="py-3 px-4">Tool</th>
                <th className="py-3 px-4">Agent / Incident</th>
                <th className="py-3 px-4">Input Summary</th>
                <th className="py-3 px-4">Output Summary</th>
                <th className="py-3 px-4">Latency</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Permission</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {calls.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    {loading ? 'Loading call history…' : error ? 'MCP call history is unavailable.' : 'No MCP tool calls logged yet.'}
                  </td>
                </tr>
              ) : (
                calls.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">#{c.id}</td>
                    <td className="py-3 px-4 font-mono font-semibold text-brand-blue">{c.tool_name}<span className={`block mt-1 font-sans text-[9px] uppercase ${c.integration_mode === 'simulated' ? 'text-amber-700' : 'text-slate-400'}`}>{c.integration_mode?.replace('_', ' ')}</span></td>
                    <td className="py-3 px-4 text-slate-600">{c.calling_agent || 'Unknown'}{c.incident_id ? ` · INC-${String(c.incident_id).padStart(6, '0')}` : ''}</td>
                    <td className="py-3 px-4 font-mono text-[11px] max-w-xs truncate text-slate-600" title={c.input_summary}>
                      {c.input_summary}
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] max-w-xs truncate text-slate-600" title={c.output_summary}>
                      {c.output_summary}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-500">{c.duration_ms}ms</td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          c.status === 'success' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          c.permission_status === 'granted' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'
                        }`}
                      >
                        {c.permission_status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

