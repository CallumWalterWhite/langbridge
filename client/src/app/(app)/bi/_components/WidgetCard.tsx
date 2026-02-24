import { memo } from 'react';
import type { DragEvent } from 'react';
import {
  BarChart3,
  Copy,
  LineChart,
  PieChart as PieChartIcon,
  Table as TableIcon,
  X,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart as RechartsLine,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

import type { BiWidget, FieldOption } from '../types';

type WidgetCardProps = {
  widget: BiWidget;
  isActive: boolean;
  isEditMode: boolean;
  onActivate: () => void;
  onRemove: () => void;
  onDuplicate: () => void;
  onAddField: (widgetId: string, field: FieldOption, targetKind?: 'dimension' | 'measure') => void;
};

const PIE_COLORS = ['#0ea5e9', '#10a37f', '#f59e0b', '#f97316', '#ec4899', '#6366f1'];

function resolveChartIcon(type: BiWidget['type']) {
  if (type === 'line') {
    return <LineChart className="h-3.5 w-3.5" />;
  }
  if (type === 'pie') {
    return <PieChartIcon className="h-3.5 w-3.5" />;
  }
  if (type === 'table') {
    return <TableIcon className="h-3.5 w-3.5" />;
  }
  return <BarChart3 className="h-3.5 w-3.5" />;
}

function WidgetCardComponent({
  widget,
  isActive,
  isEditMode,
  onActivate,
  onRemove,
  onDuplicate,
  onAddField,
}: WidgetCardProps) {
  const hasData = Boolean(widget.queryResult?.data && widget.queryResult.data.length > 0);
  const resultRows = widget.queryResult?.data ?? [];

  const columnLabelMap = new Map<string, string>();
  (widget.queryResult?.metadata ?? []).forEach((entry) => {
    if (entry && typeof entry === 'object') {
      const column = entry.column as string | undefined;
      const name = entry.name as string | undefined;
      if (column && name) {
        columnLabelMap.set(column, name);
      }
    }
  });

  const getColumnLabel = (key: string) => columnLabelMap.get(key) ?? key;

  const metricCount = widget.measures.length;
  const dimensionCount = widget.dimensions.length;
  const localFilterCount = widget.filters.length;

  const handleDragOver = (event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = 'copy';
  };

  const handleDrop = (event: DragEvent, targetKind?: 'dimension' | 'measure') => {
    event.preventDefault();
    event.stopPropagation();
    const payload = event.dataTransfer.getData('application/json');
    if (!payload) {
      return;
    }
    try {
      const field = JSON.parse(payload) as FieldOption;
      onAddField(widget.id, field, targetKind);
    } catch {
      // Ignore malformed drop payloads from non-field drags.
    }
  };

  const renderChart = () => {
    if (!hasData || !widget.queryResult) {
      return null;
    }

    const row = resultRows[0];
    const xKey = widget.chartX || Object.keys(row)[0];
    const yKey = widget.chartY || Object.keys(row).find((candidate) => candidate !== xKey) || Object.keys(row)[1];

    if (widget.type === 'bar') {
      return (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={resultRows}>
            <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="var(--panel-border)" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
            <Tooltip
              contentStyle={{
                borderRadius: '10px',
                border: '1px solid var(--panel-border)',
                boxShadow: 'var(--shadow-soft)',
                background: 'var(--panel-bg)',
                fontSize: '12px',
              }}
              cursor={{ fill: 'var(--accent-soft)' }}
            />
            <Bar dataKey={yKey} name={getColumnLabel(yKey)} fill="var(--accent)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      );
    }

    if (widget.type === 'line') {
      return (
        <ResponsiveContainer width="100%" height="100%">
          <RechartsLine data={resultRows}>
            <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="var(--panel-border)" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
            <Tooltip
              contentStyle={{
                borderRadius: '10px',
                border: '1px solid var(--panel-border)',
                boxShadow: 'var(--shadow-soft)',
                background: 'var(--panel-bg)',
                fontSize: '12px',
              }}
            />
            <Line
              type="monotone"
              dataKey={yKey}
              name={getColumnLabel(yKey)}
              stroke="var(--accent)"
              strokeWidth={2.25}
              dot={{ r: 2.4, fill: 'var(--accent)' }}
              activeDot={{ r: 4 }}
            />
          </RechartsLine>
        </ResponsiveContainer>
      );
    }

    if (widget.type === 'pie') {
      const pieData = resultRows.map((entry) => ({
        name: String((entry as Record<string, unknown>)[xKey]),
        value: Number((entry as Record<string, unknown>)[yKey]) || 0,
      }));

      return (
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip
              contentStyle={{
                borderRadius: '10px',
                border: '1px solid var(--panel-border)',
                boxShadow: 'var(--shadow-soft)',
                background: 'var(--panel-bg)',
                fontSize: '12px',
              }}
            />
            <Pie data={pieData} dataKey="value" nameKey="name" outerRadius="80%" innerRadius="42%" paddingAngle={2}>
              {pieData.map((entry, index) => (
                <Cell key={`${entry.name}-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      );
    }

    if (widget.type === 'table') {
      return (
        <div className="h-full overflow-auto rounded-xl border border-[color:var(--panel-border)]">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-[color:var(--panel-alt)] text-[color:var(--text-muted)]">
              <tr>
                {Object.keys(resultRows[0]).map((key) => (
                  <th key={key} className="px-3 py-2 font-semibold whitespace-nowrap">
                    {getColumnLabel(key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--panel-border)]">
              {resultRows.slice(0, 70).map((rowValue: Record<string, unknown>, rowIndex: number) => (
                <tr key={rowIndex} className="hover:bg-[color:var(--panel-alt)]/70">
                  {Object.values(rowValue).map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 whitespace-nowrap text-[color:var(--text-secondary)]">
                      {String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    return null;
  };

  return (
    <article
      role="group"
      aria-label={`Widget ${widget.title}`}
      className={cn(
        'bi-widget-card group relative flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border bg-[color:var(--panel-bg)] transition-all duration-200',
        isActive
          ? 'border-[color:var(--accent)] shadow-[0_12px_24px_-20px_rgba(16,163,127,0.45)]'
          : 'border-[color:var(--panel-border)] hover:border-[color:var(--border-strong)]',
      )}
      onClick={onActivate}
      onDragOver={handleDragOver}
      onDrop={(event) => handleDrop(event)}
    >
      <header className="flex items-start justify-between gap-3 border-b border-[color:var(--panel-border)] px-4 py-3">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-flex h-7 w-7 items-center justify-center rounded-lg border text-[color:var(--text-secondary)]',
                isActive
                  ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--accent)]'
                  : 'border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]',
              )}
            >
              {resolveChartIcon(widget.type)}
            </span>
            <h3 className="truncate text-sm font-semibold text-[color:var(--text-primary)]" title={widget.title}>
              {widget.title}
            </h3>
          </div>
          <p className="truncate text-[11px] text-[color:var(--text-muted)]">
            {dimensionCount} dimensions • {metricCount} measures • {localFilterCount} local filters
          </p>
        </div>

        <div
          className={cn(
            'flex items-center gap-1 transition-opacity',
            isEditMode ? 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100' : 'hidden',
          )}
        >
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-[color:var(--text-muted)] hover:text-[color:var(--accent)]"
            onClick={(event) => {
              event.stopPropagation();
              onDuplicate();
            }}
            aria-label="Duplicate widget"
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-[color:var(--text-muted)] hover:text-red-500"
            onClick={(event) => {
              event.stopPropagation();
              onRemove();
            }}
            aria-label="Remove widget"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </header>

      <div className="relative min-h-0 flex-1 px-3 pb-3 pt-2">
        {widget.isLoading ? (
          <WidgetLoadingState title={widget.statusMessage || 'Running semantic query'} progress={widget.progress ?? 0} />
        ) : null}

        {hasData ? (
          <div className="h-full min-h-[220px] rounded-xl border border-transparent bg-[color:var(--panel-bg)] p-2 transition-opacity duration-250">
            {renderChart()}
          </div>
        ) : widget.error ? (
          <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50/70 p-5 text-center">
            <p className="text-xs font-semibold text-red-700">Query failed</p>
            <p className="text-xs text-red-600/90">{widget.error}</p>
          </div>
        ) : (
          <div
            className="flex h-full min-h-[220px] flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/40 p-4 text-center text-[color:var(--text-muted)]"
            onDragOver={handleDragOver}
            onDrop={(event) => handleDrop(event)}
          >
            <div className="text-[color:var(--text-secondary)]">{resolveChartIcon(widget.type)}</div>
            <p className="text-xs font-medium">Drop fields here</p>
            <p className="text-[11px]">Drag dimensions/measures from the sidebar</p>
          </div>
        )}
      </div>
    </article>
  );
}

function WidgetLoadingState({ title, progress }: { title: string; progress: number }) {
  const safeProgress = Math.max(0, Math.min(progress, 100));
  return (
    <div className="absolute inset-x-3 top-2 z-10 rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]/95 p-3 shadow-soft backdrop-blur-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-xs font-medium text-[color:var(--text-secondary)]">{title}</p>
        <span className="text-[11px] text-[color:var(--text-muted)]">{safeProgress}%</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[color:var(--panel-alt)]">
        <div
          className="h-full rounded-full bg-[color:var(--accent)] transition-[width] duration-300"
          style={{ width: `${safeProgress}%` }}
        />
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2">
        <Skeleton className="h-2" />
        <Skeleton className="h-2" />
        <Skeleton className="h-2" />
      </div>
    </div>
  );
}

export function WidgetCardSkeleton({ title }: { title: string }) {
  return (
    <article className="bi-widget-card flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="space-y-2">
          <Skeleton className="h-3 w-20" />
          <p className="text-xs text-[color:var(--text-muted)]">{title}</p>
        </div>
        <Skeleton className="h-7 w-7 rounded-lg" />
      </div>
      <div className="mt-3 grid h-full min-h-[180px] grid-rows-4 gap-2">
        <Skeleton className="h-full" />
        <Skeleton className="h-full" />
        <Skeleton className="h-full" />
        <Skeleton className="h-full" />
      </div>
    </article>
  );
}

export const WidgetCard = memo(WidgetCardComponent, (prev, next) => {
  return prev.widget === next.widget && prev.isActive === next.isActive && prev.isEditMode === next.isEditMode;
});
