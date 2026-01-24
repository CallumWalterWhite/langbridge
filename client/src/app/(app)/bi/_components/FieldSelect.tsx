import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { FieldOption } from '../types';

type FieldSelectProps = {
  fields: FieldOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  allowEmpty?: boolean;
  emptyLabel?: string;
  filterKinds?: FieldOption['kind'][];
  className?: string;
  dropdownClassName?: string;
  inputClassName?: string;
};

export function FieldSelect({
  fields,
  value,
  onChange,
  placeholder = 'Select field',
  allowEmpty = false,
  emptyLabel = 'None',
  filterKinds,
  className,
  dropdownClassName,
  inputClassName,
}: FieldSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const containerRef = useRef<HTMLDivElement | null>(null);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return fields.filter((field) => {
      if (filterKinds && !filterKinds.includes(field.kind)) {
        return false;
      }
      if (!normalized) {
        return true;
      }
      const haystack = [
        field.label,
        field.id,
        field.tableKey ?? '',
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalized);
    });
  }, [fields, filterKinds, query]);

  const selected = fields.find((field) => field.id === value);
  const selectedLabel = selected?.label ?? '';
  const selectedMeta = selected?.tableKey ?? (selected?.kind === 'metric' ? 'Metrics' : '');

  useEffect(() => {
    if (!open) {
      setQuery('');
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleClick = (event: MouseEvent) => {
      if (!containerRef.current) {
        return;
      }
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          'flex h-10 w-full items-center justify-between rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-3 py-2 text-left text-sm text-[color:var(--text-primary)] shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--app-bg)]',
          className,
        )}
      >
        <span className="flex min-w-0 flex-col">
          <span className="truncate">
            {selectedLabel || (allowEmpty && value === '' ? emptyLabel : placeholder)}
          </span>
          {selectedMeta ? (
            <span className="text-[10px] uppercase tracking-wide text-[color:var(--text-muted)]">
              {selectedMeta}
            </span>
          ) : null}
        </span>
        <ChevronDown className="h-4 w-4 opacity-60" />
      </button>

      {open ? (
        <div
          className={cn(
            'absolute z-50 mt-2 w-full overflow-hidden rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] shadow-lg',
            dropdownClassName,
          )}
        >
          <div className="border-b border-[color:var(--panel-border)] p-2">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search fields..."
              className={cn(
                'h-8 text-xs bg-[color:var(--panel-alt)] border-0 focus-visible:ring-[color:var(--accent)]',
                inputClassName,
              )}
            />
          </div>
          <div className="max-h-64 overflow-y-auto p-1 custom-scrollbar">
            {allowEmpty ? (
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange('');
                  setOpen(false);
                }}
                className={cn(
                  'flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs transition',
                  value === '' ? 'bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]' : 'hover:bg-[color:var(--panel-alt)]',
                )}
              >
                <span className="truncate">{emptyLabel}</span>
              </button>
            ) : null}

            {filtered.map((field) => {
              const meta = field.tableKey ?? (field.kind === 'metric' ? 'Metrics' : '');
              return (
                <button
                  key={field.id}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    onChange(field.id);
                    setOpen(false);
                  }}
                  className={cn(
                    'flex w-full flex-col items-start rounded-lg px-3 py-2 text-xs transition',
                    field.id === value
                      ? 'bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]'
                      : 'hover:bg-[color:var(--panel-alt)] text-[color:var(--text-secondary)]',
                  )}
                >
                  <span className="truncate">{field.label}</span>
                  {meta ? (
                    <span className="text-[10px] uppercase tracking-wide text-[color:var(--text-muted)]">
                      {meta}
                    </span>
                  ) : null}
                </button>
              );
            })}

            {filtered.length === 0 ? (
              <div className="px-3 py-3 text-xs text-[color:var(--text-muted)]">No fields found</div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
