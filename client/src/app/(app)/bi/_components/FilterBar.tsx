import { useMemo } from 'react';
import { Filter, Plus, RotateCcw, Sparkles, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';

import { FILTER_OPERATORS } from '../types';
import type { BiWidget, FieldOption, FilterDraft } from '../types';
import { FieldSelect } from './FieldSelect';

type FilterBarProps = {
  fields: FieldOption[];
  globalFilters: FilterDraft[];
  onGlobalFiltersChange: (filters: FilterDraft[]) => void;
  onApplyFilters: () => void;
  activeWidget: BiWidget | null;
  isEditMode: boolean;
};

export function FilterBar({
  fields,
  globalFilters,
  onGlobalFiltersChange,
  onApplyFilters,
  activeWidget,
  isEditMode,
}: FilterBarProps) {
  const activeLabel = useMemo(() => activeWidget?.title || 'No widget selected', [activeWidget]);

  const addFilter = () => {
    onGlobalFiltersChange([
      ...globalFilters,
      {
        id: makeLocalId(),
        member: fields[0]?.id || '',
        operator: 'equals',
        values: '',
      },
    ]);
  };

  const updateFilter = (id: string, updates: Partial<FilterDraft>) => {
    onGlobalFiltersChange(globalFilters.map((filter) => (filter.id === id ? { ...filter, ...updates } : filter)));
  };

  const removeFilter = (id: string) => {
    onGlobalFiltersChange(globalFilters.filter((filter) => filter.id !== id));
  };

  const clearAll = () => onGlobalFiltersChange([]);

  return (
    <section className="border-b border-[color:var(--panel-border)] px-5 py-3 lg:px-6">
      <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-3 py-2.5 shadow-[0_8px_18px_-18px_rgba(15,23,42,0.55)]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] text-[color:var(--text-muted)]">
              <Filter className="h-3.5 w-3.5" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--text-secondary)]">
                Dashboard Filters
              </p>
              <p className="truncate text-[11px] text-[color:var(--text-muted)]">
                Active widget: {activeLabel}
                {activeWidget ? ` • ${activeWidget.filters.length} local override(s)` : ''}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-7 gap-1 px-2 text-[11px]" onClick={addFilter} disabled={!isEditMode}>
              <Plus className="h-3 w-3" /> Add filter
            </Button>
            <Button variant="outline" size="sm" className="h-7 gap-1 px-2 text-[11px]" onClick={clearAll} disabled={globalFilters.length === 0}>
              <RotateCcw className="h-3 w-3" /> Reset
            </Button>
            <Button size="sm" className="h-7 gap-1 rounded-full px-3 text-[11px]" onClick={onApplyFilters}>
              <Sparkles className="h-3 w-3" /> Apply
            </Button>
          </div>
        </div>

        {globalFilters.length > 0 ? (
          <div className="mt-3 grid gap-2 lg:grid-cols-2 2xl:grid-cols-3">
            {globalFilters.map((filter) => (
              <div key={filter.id} className="flex items-center gap-2 rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-2 py-2">
                <div className="flex-1">
                  <FieldSelect
                    fields={fields}
                    value={filter.member}
                    onChange={(value) => updateFilter(filter.id, { member: value })}
                    className={`h-7 rounded-lg border-0 bg-transparent px-2 text-xs shadow-none ${
                      !isEditMode ? 'pointer-events-none opacity-70' : ''
                    }`}
                    inputClassName="text-xs"
                  />
                </div>
                <Select
                  value={filter.operator}
                  onChange={(event) => updateFilter(filter.id, { operator: event.target.value })}
                  className="h-7 w-28 rounded-lg border-0 bg-[color:var(--panel-bg)] px-2 text-xs"
                  disabled={!isEditMode}
                >
                  {FILTER_OPERATORS.map((operator) => (
                    <option key={operator.value} value={operator.value}>
                      {operator.label}
                    </option>
                  ))}
                </Select>
                <Input
                  value={filter.values}
                  onChange={(event) => updateFilter(filter.id, { values: event.target.value })}
                  placeholder="Value"
                  className="h-7 w-28 rounded-lg border-0 bg-[color:var(--panel-bg)] text-xs"
                  disabled={!isEditMode}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-[color:var(--text-muted)] hover:text-red-500"
                  onClick={() => removeFilter(filter.id)}
                  aria-label="Remove global filter"
                  disabled={!isEditMode}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-3 rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/40 px-3 py-2 text-[11px] text-[color:var(--text-muted)]">
            No global filters configured. Add filters here to drive all widgets consistently.
          </div>
        )}
      </div>
    </section>
  );
}

function makeLocalId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 11);
}
