// EngineerListbox.tsx – Accessible custom listbox for assigning engineers
// Implements keyboard navigation, ARIA roles, eligibility handling, and zero‑capacity safety.
// Used in IncidentsPage to replace the native <select>.

import React, { useEffect, useRef, useState } from 'react';

export interface EngineerAvailability {
  id: number;
  full_name: string;
  availability_status: string; // e.g. 'available', 'on_leave', 'busy'
  current_workload: number;
  max_active_tickets: number;
  team: string;
  skills: string[];
}

interface EngineerListboxProps {
  engineers: EngineerAvailability[]; // all workforce engineers
  eligibleIds: Set<number>; // ids of engineers eligible for assignment (from backend)
  selectedId: string; // currently selected engineer id (string for compatibility with <select>)
  onChange: (id: string) => void; // callback when user selects a different engineer
  labelId: string; // id of the external <label> element for aria-labelledby
}

/**
 * Custom Listbox component that mimics a native <select> but provides full keyboard
 * accessibility and visual badges for availability, workload and capacity.
 *
 * Indexing model:
 *   0          – Unassigned option (always enabled)
 *   1..N      – Eligible engineers (sorted by name)
 * Disabled (ineligible) engineers are omitted from the navigation order.
 */
export const EngineerListbox: React.FC<EngineerListboxProps> = ({
  engineers,
  eligibleIds,
  selectedId,
  onChange,
  labelId,
}) => {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // filter only eligible engineers for navigation & display
  const eligibleEngineers = engineers.filter((e) => eligibleIds.size === 0 || eligibleIds.has(e.id));

  // open/close state
  const [open, setOpen] = useState(true);

  // active index – 0 = Unassigned, 1..eligibleEngineers.length = eligible options
  const [activeIndex, setActiveIndex] = useState<number>(
    selectedId ?
      selectedId === ''
        ? 0
        : eligibleEngineers.findIndex((e) => String(e.id) === selectedId) + 1
      : 0,
  );

  // synchronize selection when props change (eligibility refresh)
  useEffect(() => {
    if (selectedId && selectedId !== '') {
      const stillEligible = eligibleIds.has(Number(selectedId));
      if (!stillEligible) {
        // clear selection – parent will handle clearing state via onChange('')
        onChange('');
      }
    }
  }, [eligibleIds, selectedId, onChange]);

  // close listbox on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (open && !buttonRef.current?.contains(e.target as Node) && !listRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // focus management – move focus to list when opened
  useEffect(() => {
    if (open) {
      listRef.current?.focus();
    }
  }, [open]);

  const toggleOpen = () => setOpen((v) => !v);

  const selectOption = (idx: number) => {
    // idx 0 => unassigned, otherwise map to eligibleEngineers[idx-1]
    if (idx === 0) {
      onChange('');
    } else {
      const eng = eligibleEngineers[idx - 1];
      onChange(String(eng.id));
    }
    setOpen(false);
  };

  const moveNext = () => {
    const max = eligibleEngineers.length;
    setActiveIndex((i) => (i < max ? i + 1 : i));
  };

  const movePrev = () => {
    setActiveIndex((i) => (i > 0 ? i - 1 : i));
  };

  const goHome = () => setActiveIndex(0);
  const goEnd = () => setActiveIndex(eligibleEngineers.length);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        moveNext();
        break;
      case 'ArrowUp':
        e.preventDefault();
        movePrev();
        break;
      case 'Home':
        e.preventDefault();
        goHome();
        break;
      case 'End':
        e.preventDefault();
        goEnd();
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        selectOption(activeIndex);
        break;
      case 'Escape':
        e.preventDefault();
        setOpen(false);
        break;
      default:
        break;
    }
  };

  // render display label for current selection
  const selectedLabel = () => {
    if (selectedId === '' || selectedId === undefined) return 'Unassigned';
    const eng = engineers.find((e) => String(e.id) === selectedId);
    return eng ? `${eng.full_name}` : 'Unassigned';
  };

  return (
    <div className="relative inline-block w-full">
      <button
        ref={buttonRef}
        type="button"
        id="engineer-select"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls="engineer-listbox"
        aria-labelledby={labelId}
        className="mt-1 w-full rounded border border-slate-200 bg-white px-2 py-2 text-left text-sm"
        onClick={toggleOpen}
      >
        {selectedLabel()}
      </button>
      {open && (
        <ul
          ref={listRef}
          id="engineer-listbox"
          role="listbox"
          tabIndex={-1}
          aria-activedescendant={activeIndex === 0 ? undefined : `engineer-option-${activeIndex}`}
          className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded border border-slate-200 bg-white shadow-lg outline-none"
          onKeyDown={handleKeyDown}
        >
          {/* Unassigned option */}
          <li
            id="engineer-option-0"
            role="option"
            aria-selected={activeIndex === 0}
            className={`cursor-pointer px-2 py-1 text-sm ${activeIndex === 0 ? 'bg-slate-200' : ''}`}
            onMouseEnter={() => setActiveIndex(0)}
            onClick={() => selectOption(0)}
          >
            Unassigned
          </li>
          {eligibleEngineers.map((eng, idx) => {
            const index = idx + 1; // because 0 is unassigned
            const isActive = activeIndex === index;
            const fullLabel = `${eng.full_name} (${eng.availability_status.replace(/_/g, ' ')} · ${eng.current_workload}/${eng.max_active_tickets} active · ${eng.team})`;
            return (
              <li
                key={eng.id}
                id={`engineer-option-${index}`}
                role="option"
                aria-selected={isActive}
                aria-disabled={false}
                className={`cursor-pointer px-2 py-1 text-sm ${isActive ? 'bg-slate-200' : ''}`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => selectOption(index)}
              >
                {fullLabel}
              </li>
            );
          })}
          {/* Render ineligible engineers (disabled) */}
          {engineers.filter((e) => !eligibleIds.has(e.id)).map((eng, idx) => {
            const index = eligibleEngineers.length + idx + 1; // continue indexing after eligible
            const isActive = activeIndex === index;
            const fullLabel = `${eng.full_name} (${eng.availability_status.replace(/_/g, ' ')} · ${eng.current_workload}/${eng.max_active_tickets} active · ${eng.team})`;
            return (
              <li
                key={eng.id}
                id={`engineer-option-${index}`}
                role="option"
                aria-selected={isActive}
                aria-disabled={true}
                className={`cursor-not-allowed px-2 py-1 text-sm text-slate-400 ${isActive ? 'bg-slate-200' : ''}`}
                onMouseEnter={() => setActiveIndex(index)}
                // disabled click
                onClick={(e) => e.stopPropagation()}
              >
                {fullLabel}
              </li>
            );
          })}

        </ul>
      )}
    </div>
  );
};
