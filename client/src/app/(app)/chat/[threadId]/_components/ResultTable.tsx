import type { ThreadTabularResult } from '@/orchestration/threads';

type ResultTableProps = {
  result: ThreadTabularResult;
  maxPreviewRows?: number;
};

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '—';
  }

  if (typeof value === 'number') {
    const absValue = Math.abs(value);
    if (absValue >= 1000) {
      return value.toLocaleString();
    }
    if (Number.isInteger(value)) {
      return value.toString();
    }
    return value.toFixed(3).replace(/\.?0+$/, '');
  }

  if (value instanceof Date) {
    return value.toISOString();
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  return String(value);
};

const normaliseRow = (columns: string[], row: unknown): unknown[] => {
  if (Array.isArray(row)) {
    if (columns.length === 0) {
      return row;
    }
    if (row.length >= columns.length) {
      return row.slice(0, columns.length);
    }
    return [...row, ...Array(columns.length - row.length).fill(null)];
  }

  if (row && typeof row === 'object') {
    const record = row as Record<string, unknown>;
    if (columns.length > 0) {
      return columns.map((column) => record[column]);
    }
    return Object.values(record);
  }

  return [row];
};

const formatElapsed = (elapsedMs?: number | null): string | null => {
  if (elapsedMs === null || elapsedMs === undefined) {
    return null;
  }
  if (elapsedMs < 1000) {
    return `${elapsedMs} ms`;
  }
  const seconds = elapsedMs / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(2)} s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds - minutes * 60;
  return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
};

export function ResultTable({ result, maxPreviewRows = 10 }: ResultTableProps) {
  const columns = Array.isArray(result.columns) ? result.columns : [];
  const rows = Array.isArray(result.rows) ? result.rows : [];
  const previewRows = rows.slice(0, maxPreviewRows);
  const normalised = previewRows.map((row) => normaliseRow(columns, row));
  const truncatedCount = rows.length > maxPreviewRows ? rows.length - maxPreviewRows : 0;

  const displayColumns =
    columns.length > 0
      ? columns
      : normalised.length > 0
      ? normalised[0].map((_, index) => `Column ${index + 1}`)
      : [];

  const elapsedLabel = formatElapsed(result.elapsedMs);

  if (displayColumns.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-6 text-center text-xs text-[color:var(--text-muted)]">
        No tabular data available for this response.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]">
        <table className="min-w-full divide-y divide-[color:var(--panel-border)] text-left text-xs sm:text-sm">
          <thead className="bg-[color:var(--panel-bg)]">
            <tr>
              {displayColumns.map((column) => (
                <th key={column} scope="col" className="px-4 py-3 font-semibold uppercase tracking-wider text-[10px] text-[color:var(--text-muted)] sm:text-[11px]">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--panel-border)]">
            {normalised.map((row, rowIndex) => (
              <tr key={rowIndex} className="odd:bg-[color:var(--panel-alt)]/60">
                {row.map((value, cellIndex) => (
                  <td key={`${rowIndex}-${cellIndex}`} className="px-4 py-3 align-top text-[color:var(--text-secondary)]">
                    {formatValue(value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-[color:var(--text-muted)]">
        {result.rowCount !== null && result.rowCount !== undefined ? (
          <span>{result.rowCount.toLocaleString()} rows total</span>
        ) : null}
        {elapsedLabel ? <span>Query elapsed {elapsedLabel}</span> : null}
        {truncatedCount > 0 ? <span>{truncatedCount.toLocaleString()} additional rows not shown</span> : null}
      </div>
    </div>
  );
}
