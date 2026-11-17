// AssignEngineerModal.tsx – Modal for assigning an engineer to an incident
import React, { useState } from 'react';
import { EngineerListbox, EngineerAvailability } from './EngineerListbox';
import { X } from 'lucide-react';

interface AssignEngineerModalProps {
  incidentId: number;
  currentEngineerId?: number;
  engineers: EngineerAvailability[];
  eligibleIds: Set<number>;
  lockVersion: number;
  onClose: () => void;
  /** Called with the selected engineer id (or undefined for unassigned) */
  onAssign: (engineerId?: number) => Promise<void>;
}

export const AssignEngineerModal: React.FC<AssignEngineerModalProps> = ({
  incidentId,
  currentEngineerId,
  engineers,
  eligibleIds,
  lockVersion,
  onClose,
  onAssign,
}) => {
  const [selectedId, setSelectedId] = useState<string>(currentEngineerId ? String(currentEngineerId) : '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>('');

  const handleConfirm = async () => {
    setBusy(true);
    setError('');
    try {
      const engId = selectedId ? Number(selectedId) : undefined;
      await onAssign(engId);
      onClose();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.toLowerCase().includes('409') || msg.toLowerCase().includes('conflict')) {
        setError('Incident was modified by another user. Please refresh and try again.');
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Assign Engineer">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
        <div className="flex items-start justify-between">
          <h3 className="text-lg font-semibold text-slate-900">Assign Engineer</h3>
          <button onClick={onClose} aria-label="Close dialog">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>
        {error && (
          <div role="alert" className="rounded bg-rose-50 p-2 text-rose-700 text-sm">
            {error}
          </div>
        )}
        <div>
          <label id="assign-engineer-label" className="text-xs font-medium text-slate-600" htmlFor="engineer-select">
            Engineer
          </label>
          <EngineerListbox
            engineers={engineers}
            eligibleIds={eligibleIds}
            selectedId={selectedId}
            onChange={setSelectedId}
            labelId="assign-engineer-label"
          />
        </div>
        <div className="flex justify-end gap-2 mt-2">
          <button
            type="button"
            disabled={busy}
            onClick={onClose}
            className="rounded px-3 py-1.5 text-xs font-medium text-slate-700 border border-slate-200 hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={handleConfirm}
            className="rounded px-3 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700"
          >
            {busy ? 'Assigning…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
};
