import type { ThreadTabularResult, ThreadVisualizationSpec } from '@/orchestration/threads';

type VisualizationPreviewProps = {
  visualization: ThreadVisualizationSpec;
  result?: ThreadTabularResult;
};

const normaliseRecord = (columns: string[], row: Record<string, unknown> | unknown[]): Record<string, unknown> => {
  if (Array.isArray(row)) {
    if (columns.length === 0) {
      return row.reduce<Record<string, unknown>>((accumulator, value, index) => {
        accumulator[`column_${index + 1}`] = value;
        return accumulator;
      }, {});
    }

    return columns.reduce<Record<string, unknown>>((accumulator, column, index) => {
      accumulator[column] = row[index];
      return accumulator;
    }, {});
  }

  return row;
};

const stringifyOptions = (options?: Record<string, unknown> | null): string | null => {
  if (!options || Object.keys(options).length === 0) {
    return null;
  }
  return JSON.stringify(options, null, 2);
};

export function VisualizationPreview({ visualization, result }: VisualizationPreviewProps) {
  if (!visualization || Object.keys(visualization).length === 0) {
    return null;
  }

  const { chartType, title, x, y, groupBy, options } = visualization;
  const measureFields = Array.isArray(y) ? y : y ? [y] : [];
  const dimensionLabel = x ?? (groupBy ?? null);

  const rows = Array.isArray(result?.rows) ? result?.rows ?? [] : [];
  const columns = Array.isArray(result?.columns) ? result?.columns ?? [] : [];
  const sampleRows = rows.slice(0, 3).map((row) => normaliseRecord(columns, row as Record<string, unknown> | unknown[]));
  const optionsPreview = stringifyOptions(options ?? undefined);

  return (
    <section className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-5 shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-[color:var(--text-primary)]">Visualization</h3>
          {title ? <p className="text-xs text-[color:var(--text-muted)]">{title}</p> : null}
        </div>
        {chartType ? (
          <span className="inline-flex items-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
            {chartType}
          </span>
        ) : null}
      </div>

      <dl className="mt-4 grid gap-3 text-xs text-[color:var(--text-secondary)] sm:grid-cols-2">
        {dimensionLabel ? (
          <div>
            <dt className="font-semibold text-[color:var(--text-primary)]">Dimension</dt>
            <dd className="mt-1 break-words text-[color:var(--text-secondary)]">{dimensionLabel}</dd>
          </div>
        ) : null}
        {measureFields.length > 0 ? (
          <div>
            <dt className="font-semibold text-[color:var(--text-primary)]">Measures</dt>
            <dd className="mt-1 space-y-1">
              {measureFields.map((field) => (
                <span key={field} className="block rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-2 py-1 text-[10px] uppercase tracking-[0.08em] text-[color:var(--text-muted)]">
                  {field}
                </span>
              ))}
            </dd>
          </div>
        ) : null}
        {groupBy ? (
          <div>
            <dt className="font-semibold text-[color:var(--text-primary)]">Group by</dt>
            <dd className="mt-1 text-[color:var(--text-secondary)]">{groupBy}</dd>
          </div>
        ) : null}
      </dl>

      {optionsPreview ? (
        <div className="mt-4 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]/60">
          <details className="group">
            <summary className="cursor-pointer list-none px-4 py-3 text-xs font-semibold text-[color:var(--text-muted)] transition hover:text-[color:var(--text-primary)]">
              Chart options
            </summary>
            <pre className="overflow-x-auto px-4 pb-4 text-[10px] leading-relaxed text-[color:var(--text-secondary)]">
              {optionsPreview}
            </pre>
          </details>
        </div>
      ) : null}

      {sampleRows.length > 0 ? (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">Sample data</p>
          <div className="space-y-2 text-[10px]">
            {sampleRows.map((row, index) => (
              <pre
                key={index}
                className="overflow-x-auto rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-3 text-[color:var(--text-secondary)]"
              >
                {JSON.stringify(row, null, 2)}
              </pre>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
