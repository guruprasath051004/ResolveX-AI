import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  FileCheck2,
  FileText,
  Filter,
  FlaskConical,
  Play,
  PlayCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  Terminal,
  Users,
  XCircle,
} from 'lucide-react';
import {
  exportLabReport,
  listLabScenarios,
  runAllLabScenarios,
  runLabScenario,
} from '../services/api';

interface ScenarioDef {
  id: string;
  name: string;
  category: string;
  description: string;
  expected_outcome: string;
}

interface ScenarioResult {
  scenario_id: string;
  run_id: string;
  name: string;
  category: string;
  description: string;
  execution_status: string;
  verdict: 'PASS' | 'FAIL';
  passed_checks: string[];
  failed_checks: string[];
  warnings: string[];
  input_conditions: Record<string, any>;
  expected_outcome: string;
  actual_outcome: string;
  agent_sequence: string[];
  mcp_calls: Array<{ tool: string; status: string; error?: string; simulated: boolean; result?: any }>;
  assignment_decision?: { id?: number; name?: string; email?: string; team?: string; full_name?: string };
  approval_decision?: { required: boolean; status: string; approver_role?: string };
  sla_impact?: { priority?: string; resolution_target_hours?: number; is_breached?: boolean };
  notifications_generated: string[];
  audit_events: string[];
  execution_steps: string[];
  execution_duration_ms: number;
  simulated: boolean;
  executed_at: string;
}

export const ScenarioLabPage: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  // Execution states
  const [runningScenarioId, setRunningScenarioId] = useState<string | null>(null);
  const [batchRunning, setBatchRunning] = useState(false);
  const [selectedResult, setSelectedResult] = useState<ScenarioResult | null>(null);
  const [latestResults, setLatestResults] = useState<Record<string, ScenarioResult>>({});
  const [batchSummary, setBatchSummary] = useState<{
    total: number;
    passed: number;
    failed: number;
    warnings: number;
    pass_rate_pct: number;
    duration_ms: number;
  } | null>(null);
  const [exporting, setExporting] = useState(false);

  const fetchScenarios = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await listLabScenarios();
      setScenarios(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load Scenario Testing Lab library.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScenarios();
  }, []);

  const categories = ['All', ...Array.from(new Set(scenarios.map((s) => s.category || 'General')))];

  const filteredScenarios = scenarios.filter((s) => {
    const matchesCategory = selectedCategory === 'All' || s.category === selectedCategory;
    const matchesSearch =
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleRunScenario = async (scenario: ScenarioDef) => {
    try {
      setRunningScenarioId(scenario.id);
      setError('');
      const res = await runLabScenario(scenario.id);
      setLatestResults((prev) => ({ ...prev, [scenario.id]: res }));
      setSelectedResult(res);
    } catch (err: any) {
      setError(err?.message || `Execution failed for ${scenario.name}`);
    } finally {
      setRunningScenarioId(null);
    }
  };

  const handleRunAll = async () => {
    try {
      setBatchRunning(true);
      setError('');
      const batch = await runAllLabScenarios();
      const resultsMap: Record<string, ScenarioResult> = {};
      batch.results.forEach((r: ScenarioResult) => {
        resultsMap[r.scenario_id] = r;
      });
      setLatestResults(resultsMap);
      setBatchSummary({
        total: batch.total_scenarios,
        passed: batch.passed_count,
        failed: batch.failed_count,
        warnings: batch.warning_count,
        pass_rate_pct: batch.pass_rate_pct,
        duration_ms: batch.total_duration_ms,
      });
      if (batch.results.length > 0) {
        setSelectedResult(batch.results[0]);
      }
    } catch (err: any) {
      setError(err?.message || 'Batch scenario run failed.');
    } finally {
      setBatchRunning(false);
    }
  };

  const handleExport = async (format: 'json' | 'csv') => {
    try {
      setExporting(true);
      const data = await exportLabReport(format);
      if (format === 'csv') {
        const url = window.URL.createObjectURL(data as Blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `resolvex_scenario_lab_audit_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
      } else {
        const jsonBlob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(jsonBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `resolvex_scenario_lab_audit_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
      }
    } catch (err: any) {
      setError(err?.message || `Failed to export ${format.toUpperCase()} report.`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto h-full overflow-y-auto bg-slate-50">
      {/* Top Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-violet-600 flex items-center justify-center text-white shadow-sm">
              <FlaskConical className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 leading-tight">
                Scenario Testing Lab
              </h1>
              <p className="text-xs text-slate-500">
                Deterministic edge-case simulation environment with strict transactional rollback isolation
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={() => handleExport('json')}
            disabled={exporting}
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50"
            title="Download JSON Audit Report"
          >
            <Download className="w-3.5 h-3.5" />
            <span>JSON</span>
          </button>
          <button
            onClick={() => handleExport('csv')}
            disabled={exporting}
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50"
            title="Download CSV Audit Report"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>CSV</span>
          </button>
          <button
            onClick={handleRunAll}
            disabled={batchRunning}
            className="flex items-center space-x-1.5 px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white rounded-lg text-xs font-bold shadow-md shadow-violet-200 transition disabled:opacity-50"
          >
            <PlayCircle className={`w-4 h-4 ${batchRunning ? 'animate-spin' : ''}`} />
            <span>{batchRunning ? 'Running 20 Scenarios…' : 'Run All 20 Scenarios'}</span>
          </button>
        </div>
      </div>

      {/* Strict Isolation Notice */}
      <div className="rounded-xl border border-violet-200/80 bg-violet-50/60 p-3.5 flex items-start space-x-3 text-xs text-violet-900">
        <ShieldCheck className="w-4 h-4 text-violet-600 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold">Strict Test Isolation Active:</span> Simulations execute in ephemeral rollback
          transactions with dedicated mock namespaces. Zero test data leaks into production incident queues, engineer
          workloads, or employee notifications.
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Summary KPI Cards (Visible when batch runs or results exist) */}
      {batchSummary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Scenarios</span>
            <p className="text-2xl font-black text-slate-900 mt-1">{batchSummary.total}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">Passed</span>
            <p className="text-2xl font-black text-emerald-600 mt-1">{batchSummary.passed}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-rose-600">Failed</span>
            <p className="text-2xl font-black text-rose-600 mt-1">{batchSummary.failed}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-600">Pass Rate</span>
            <p className="text-2xl font-black text-slate-900 mt-1">{batchSummary.pass_rate_pct}%</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600">Total Duration</span>
            <p className="text-2xl font-black text-slate-900 mt-1">{batchSummary.duration_ms} ms</p>
          </div>
        </div>
      )}

      {/* Main Grid: Left = Scenario Library, Right = Detailed Execution Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Scenarios List (5 cols) */}
        <div className="lg:col-span-5 space-y-3">
          {/* Filters & Search */}
          <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-sm space-y-2.5">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search 20 scenarios..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-violet-500"
              />
            </div>
            <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-[11px]">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-2.5 py-1 rounded-md font-medium shrink-0 transition ${
                    selectedCategory === cat
                      ? 'bg-violet-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Scenarios Scroll List */}
          <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1">
            {loading ? (
              <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-xs text-slate-500">
                Loading Scenario Testing Lab definitions…
              </div>
            ) : filteredScenarios.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-xs text-slate-500">
                No scenarios match the selected filter.
              </div>
            ) : (
              filteredScenarios.map((scenario) => {
                const latest = latestResults[scenario.id];
                const isRunning = runningScenarioId === scenario.id;
                const isSelected = selectedResult?.scenario_id === scenario.id;

                return (
                  <div
                    key={scenario.id}
                    onClick={() => latest && setSelectedResult(latest)}
                    className={`bg-white rounded-xl border p-3.5 transition cursor-pointer shadow-sm hover:border-slate-300 ${
                      isSelected
                        ? 'border-violet-500 ring-1 ring-violet-500'
                        : 'border-slate-200'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                            {scenario.id.replace('_', ' ')}
                          </span>
                          <span className="text-[10px] font-medium text-slate-400">
                            {scenario.category}
                          </span>
                        </div>
                        <h3 className="text-xs font-bold text-slate-900 mt-1">{scenario.name}</h3>
                        <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-2">{scenario.description}</p>
                      </div>

                      <div className="flex flex-col items-end gap-1.5 shrink-0">
                        {latest ? (
                          <span
                            className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase ${
                              latest.verdict === 'PASS'
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'bg-rose-100 text-rose-700'
                            }`}
                          >
                            {latest.verdict === 'PASS' ? (
                              <CheckCircle2 className="w-3 h-3" />
                            ) : (
                              <XCircle className="w-3 h-3" />
                            )}
                            <span>{latest.verdict}</span>
                          </span>
                        ) : null}

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRunScenario(scenario);
                          }}
                          disabled={isRunning || batchRunning}
                          className="px-2.5 py-1 bg-slate-50 hover:bg-violet-50 hover:text-violet-700 text-slate-700 rounded-lg border border-slate-200 text-[11px] font-semibold flex items-center space-x-1 transition disabled:opacity-50"
                        >
                          <Play className={`w-3 h-3 ${isRunning ? 'animate-spin' : ''}`} />
                          <span>{isRunning ? 'Running…' : 'Run'}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Execution Inspector (7 cols) */}
        <div className="lg:col-span-7">
          {selectedResult ? (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
              {/* Result Header */}
              <div className="flex items-start justify-between border-b border-slate-100 pb-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-violet-100 text-violet-800">
                      {selectedResult.scenario_id.replace('_', ' ')}
                    </span>
                    <span className="text-[10px] font-bold text-slate-400">
                      Run ID: {selectedResult.run_id}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-slate-900 mt-1">{selectedResult.name}</h2>
                  <p className="text-xs text-slate-500 mt-0.5">{selectedResult.description}</p>
                </div>

                <div className="flex flex-col items-end shrink-0">
                  <span
                    className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider shadow-sm ${
                      selectedResult.verdict === 'PASS'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-rose-600 text-white'
                    }`}
                  >
                    {selectedResult.verdict === 'PASS' ? (
                      <CheckCircle2 className="w-4 h-4" />
                    ) : (
                      <XCircle className="w-4 h-4" />
                    )}
                    <span>{selectedResult.verdict}</span>
                  </span>
                  <span className="text-[10px] text-slate-400 font-medium mt-1 flex items-center space-x-1">
                    <Clock className="w-3 h-3" />
                    <span>{selectedResult.execution_duration_ms} ms</span>
                  </span>
                </div>
              </div>

              {/* Expected vs Actual Comparison */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-slate-50 rounded-xl p-4 border border-slate-100 text-xs">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Expected Outcome</span>
                  <p className="font-medium text-slate-700 mt-1 leading-relaxed">
                    {selectedResult.expected_outcome}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Actual Outcome</span>
                  <p className="font-semibold text-slate-900 mt-1 leading-relaxed">
                    {selectedResult.actual_outcome}
                  </p>
                </div>
              </div>

              {/* Verification Checks & Warnings */}
              <div className="space-y-3">
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Verification Assertions
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {selectedResult.passed_checks.map((chk, i) => (
                    <div
                      key={i}
                      className="flex items-center space-x-2 bg-emerald-50/70 text-emerald-800 border border-emerald-200/80 rounded-lg px-2.5 py-1.5 font-medium"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      <span>{chk}</span>
                    </div>
                  ))}
                  {selectedResult.warnings.map((warn, i) => (
                    <div
                      key={i}
                      className="flex items-center space-x-2 bg-amber-50 text-amber-800 border border-amber-200 rounded-lg px-2.5 py-1.5 font-medium"
                    >
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                      <span>{warn}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Agent Orchestration Sequence */}
              {selectedResult.agent_sequence?.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    Agent Swarm Handoff Sequence
                  </h4>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {selectedResult.agent_sequence.map((agent, i) => (
                      <React.Fragment key={i}>
                        <span className="px-2.5 py-1 bg-navy-900 text-white rounded-lg text-xs font-semibold shadow-xs">
                          {agent}
                        </span>
                        {i < selectedResult.agent_sequence.length - 1 && (
                          <ArrowRight className="w-3 h-3 text-slate-400 shrink-0" />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              )}

              {/* MCP Tool Activity */}
              {selectedResult.mcp_calls?.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    MCP Tool Executions
                  </h4>
                  <div className="space-y-1.5">
                    {selectedResult.mcp_calls.map((call, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between text-xs bg-purple-50/60 border border-purple-200 rounded-lg px-3 py-2"
                      >
                        <div className="flex items-center space-x-2">
                          <Terminal className="w-3.5 h-3.5 text-brand-violet" />
                          <code className="font-mono text-purple-900 font-bold">{call.tool}</code>
                          {call.simulated && (
                            <span className="px-1.5 py-0.2 bg-purple-200 text-purple-800 rounded text-[9px] font-semibold uppercase">
                              Simulated
                            </span>
                          )}
                        </div>
                        <span
                          className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                            call.status === 'success'
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {call.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Execution Steps Log */}
              <div className="space-y-2">
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Execution Telemetry Log
                </h4>
                <div className="bg-slate-900 text-slate-200 rounded-xl p-3.5 text-xs font-mono space-y-1 overflow-x-auto max-h-48">
                  {selectedResult.execution_steps.map((st, i) => (
                    <div key={i} className="flex items-start space-x-2">
                      <span className="text-slate-500 select-none">&gt;</span>
                      <span className="text-emerald-400">{st}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center text-slate-500">
              <FlaskConical className="w-10 h-10 mx-auto text-slate-300 mb-3" />
              <h3 className="text-sm font-bold text-slate-700">No Scenario Selected</h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
                Select a scenario from the library on the left or click "Run All 20 Scenarios" to execute the full
                enterprise test suite.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
