import React, { useEffect, useState } from 'react';
import { AlertCircle, Check, FileCheck2, RefreshCw, ShieldAlert, X } from 'lucide-react';
import { approveRequest, getApprovals, rejectRequest } from '../services/api';

type ApprovalRecord = {
  id: number;
  request_type: string;
  status: string;
  requester_name: string;
  created_at: string | null;
  requested_action: unknown;
  details: {
    incident_id?: number;
    ticket_id?: string;
    description?: string;
    status?: string;
    priority?: string;
    service_request_id?: number;
    type?: string;
  } | null;
  decided_by: { id: number; name: string } | null;
  decided_at: string | null;
  decision_reason: string | null;
  execution_result: string | null;
};

export interface ApprovalsPageProps {
  onNavigate?: (page: string, incidentId?: number) => void;
}

export const ApprovalsPage: React.FC<ApprovalsPageProps> = ({ onNavigate }) => {
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [error, setError] = useState('');

  const fetchApprovals = async () => {
    try {
      setLoading(true);
      setError('');
      setApprovals(await getApprovals());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load approvals.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchApprovals();
  }, []);

  const decide = async (approval: ApprovalRecord, decision: 'approve' | 'reject') => {
    const verb = decision === 'approve' ? 'approve' : 'reject';
    if (!window.confirm(`Are you sure you want to ${verb} approval #${approval.id}?`)) return;
    try {
      setActionLoading(approval.id);
      setError('');
      if (decision === 'approve') await approveRequest(approval.id, reasons[approval.id]);
      else await rejectRequest(approval.id, reasons[approval.id]);
      await fetchApprovals();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Failed to ${verb} request.`);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="h-full overflow-y-auto bg-slate-50 p-5 lg:p-8">
      <header className="mb-6 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Approval Review</h2>
          <p className="mt-1 text-xs text-slate-500">Review the requester, linked ticket, requested action, and execution outcome.</p>
        </div>
        <button onClick={() => void fetchApprovals()} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700"><RefreshCw className="h-4 w-4" /> Refresh</button>
      </header>

      <div className="mb-5 flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-900">
        <ShieldAlert className="h-5 w-5 shrink-0 text-blue-700" />
        <p><strong>Approval gate:</strong> sensitive operations remain pending until an authorized reviewer approves them. Approval and execution outcomes are recorded separately.</p>
      </div>
      {error && <div role="alert" className="mb-4 flex gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}

      <div className="space-y-4">
        {loading ? <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">Loading approval records…</p>
          : approvals.length === 0 ? <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">No approval records found.</p>
            : approvals.map((approval) => (
              <article key={approval.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs font-bold text-violet-700">Approval #{approval.id} · {approval.request_type}</p>
                    <h3 className="mt-1 text-sm font-bold text-slate-900">Requested by {approval.requester_name}</h3>
                    <p className="mt-1 text-xs text-slate-500">Submitted {approval.created_at ? new Date(approval.created_at).toLocaleString() : 'time unavailable'}</p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${approval.status === 'approved' ? 'bg-emerald-100 text-emerald-800' : approval.status === 'rejected' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'}`}>{approval.status}</span>
                </div>

                {approval.details && (
                  <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs">
                    <div className="flex items-center justify-between font-semibold text-slate-800">
                      {(approval.details.incident_id || typeof approval.details.ticket_id === 'number') ? (
                        <button
                          type="button"
                          onClick={() => onNavigate?.('incidents', approval.details?.incident_id || Number(approval.details?.ticket_id))}
                          className="font-mono text-brand-blue hover:underline font-bold"
                          title="Open in Incidents Queue"
                        >
                          {typeof approval.details.ticket_id === 'string'
                            ? approval.details.ticket_id
                            : `INC-${String(approval.details.incident_id || approval.details.ticket_id).padStart(6, '0')}`}
                        </button>
                      ) : (
                        <span>{approval.details.ticket_id || `Service request #${approval.details.service_request_id || '—'}`}</span>
                      )}
                      <span className="text-slate-500 font-normal">{approval.details.type || approval.details.priority || ''}</span>
                    </div>
                    <p className="mt-1 text-slate-600">{approval.details.description || 'No request details recorded.'}</p>
                    <p className="mt-1 text-slate-500">Current status: {approval.details.status || 'unknown'}</p>
                  </div>
                )}
                {approval.requested_action !== null && <pre className="mt-3 max-h-40 overflow-auto rounded-lg border border-slate-200 p-3 text-[11px] text-slate-600">{JSON.stringify(approval.requested_action, null, 2)}</pre>}
                {approval.status === 'pending' ? (
                  <div className="mt-4">
                    <label className="text-xs font-medium text-slate-700">Reviewer comments
                      <textarea value={reasons[approval.id] || ''} onChange={(event) => setReasons((current) => ({ ...current, [approval.id]: event.target.value }))} maxLength={1000} rows={2} className="mt-1 w-full rounded-lg border border-slate-200 p-2" placeholder="Reason or conditions for this decision (optional)" />
                    </label>
                    <div className="mt-2 flex justify-end gap-2">
                      <button disabled={actionLoading === approval.id} onClick={() => void decide(approval, 'reject')} className="inline-flex items-center gap-1 rounded bg-rose-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"><X className="h-3.5 w-3.5" /> Reject</button>
                      <button disabled={actionLoading === approval.id} onClick={() => void decide(approval, 'approve')} className="inline-flex items-center gap-1 rounded bg-emerald-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"><Check className="h-3.5 w-3.5" /> Approve</button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-600">
                    <p><FileCheck2 className="mr-1 inline h-3.5 w-3.5" />{approval.status} by {approval.decided_by?.name || 'Reviewer'} · {approval.decided_at ? new Date(approval.decided_at).toLocaleString() : 'time unavailable'}</p>
                    {approval.decision_reason && <p className="mt-1">Comment: {approval.decision_reason}</p>}
                    {approval.execution_result && <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-2 text-[11px]">{approval.execution_result}</pre>}
                  </div>
                )}
              </article>
            ))}
      </div>
    </div>
  );
};
