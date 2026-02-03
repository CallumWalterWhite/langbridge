import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { ThreadTabularResult, ThreadVisualizationSpec } from '@/orchestration/threads';

type VisualizationPreviewProps = {
  visualization: ThreadVisualizationSpec;
  result?: ThreadTabularResult;
};

type RawVisualizationSpec = ThreadVisualizationSpec & Record<string, unknown>;
type ChartRow = Record<string, string | number | null>;

const CHART_COLORS = ['#6366F1', '#EC4899', '#10B981', '#F97316', '#0EA5E9', '#FBBF24', '#A855F7'];

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'string') {
    let cleaned = value.trim();
    if (!cleaned) {
      return null;
    }
    cleaned = cleaned.replaceAll(',', '');
    cleaned = cleaned.replaceAll('$', '').replaceAll('£', '').replaceAll('€', '');
    if (cleaned.endsWith('%')) {
      cleaned = cleaned.slice(0, -1);
    }
    const parsedString = Number(cleaned);
    return Number.isFinite(parsedString) ? parsedString : null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const toRecord = (columns: string[], row: unknown): Record<string, unknown> => {
  if (Array.isArray(row)) {
    const header = columns.length > 0 ? columns : row.map((_, index) => `column_${index + 1}`);
    return header.reduce<Record<string, unknown>>((accumulator, column, index) => {
      accumulator[column] = row[index];
      return accumulator;
    }, {});
  }

  if (row && typeof row === 'object') {
    return row as Record<string, unknown>;
  }

  const key = columns[0] ?? 'value';
  return { [key]: row };
};

const normaliseSpec = (spec: RawVisualizationSpec) => {
  const chartType = (spec.chartType ?? spec.chart_type ?? null) as string | null;
  const title = (spec.title ?? spec.chart_title ?? null) as string | null;
  const x = (spec.x ?? spec.x_axis ?? null) as string | null;
  const groupBy = (spec.groupBy ?? spec.group_by ?? null) as string | null;
  const yValue = spec.y ?? spec.y_axis ?? null;
  const y = Array.isArray(yValue)
    ? (yValue as string[])
    : typeof yValue === 'string' && yValue.length > 0
    ? yValue
    : null;
  return { chartType, title, x, y, groupBy };
};

const ChartPlaceholder = ({ message }: { message: string }) => (
  <div className="mt-4 rounded-xl border border-dashed border-[color:var(--panel-border)]/70 bg-[color:var(--panel-alt)]/45 px-3 py-2 text-xs text-[color:var(--text-muted)]">
    {message}
  </div>
);

export function VisualizationPreview({ visualization, result }: VisualizationPreviewProps) {
  if (!visualization || Object.keys(visualization).length === 0) {
    return null;
  }

  const { chartType, title, x, y, groupBy } = normaliseSpec(visualization as RawVisualizationSpec);
  const rows = Array.isArray(result?.rows) ? result.rows : [];
  const columns = Array.isArray(result?.columns) ? result.columns : [];
  const records = rows.map((row) => toRecord(columns, row));
  const displayColumns = columns.length > 0 ? columns : records[0] ? Object.keys(records[0]) : [];
  const measureFields = Array.isArray(y) ? y : y ? [y] : [];

  const dimensionKey =
    x ??
    (chartType?.toLowerCase() === 'scatter'
      ? null
      : displayColumns.find((column) => !measureFields.includes(column)) ?? null);

  const chartVariant = chartType?.toLowerCase() ?? 'table';

  const renderCategoricalChart = (variant: 'bar' | 'line') => {
    if (!dimensionKey) {
      return <ChartPlaceholder message="Visualization is missing a dimension to plot." />;
    }

    const measures =
      measureFields.length > 0
        ? measureFields
        : displayColumns.filter((column) => column !== dimensionKey).slice(0, 2);

    if (measures.length === 0) {
      return <ChartPlaceholder message="Visualization did not specify any numeric measures." />;
    }

    const data = records
      .map((record) => {
        const dimensionValue = record[dimensionKey];
        if (dimensionValue === undefined || dimensionValue === null) {
          return null;
        }

        const entry: ChartRow = { [dimensionKey]: String(dimensionValue) };
        let hasValue = false;
        measures.forEach((measure) => {
          const numeric = toNumber(record[measure]);
          if (numeric !== null) {
            entry[measure] = numeric;
            hasValue = true;
          } else {
            entry[measure] = null;
          }
        });
        return hasValue ? entry : null;
      })
      .filter((entry): entry is ChartRow => entry !== null);

    if (data.length === 0) {
      return <ChartPlaceholder message="Not enough numeric rows to render the visualization." />;
    }

    const ChartComponent = variant === 'bar' ? BarChart : LineChart;
    const SeriesComponent = variant === 'bar' ? Bar : Line;

    return (
      <div className="mt-4 h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ChartComponent data={data}>
            <CartesianGrid stroke="rgba(148, 163, 184, 0.35)" strokeDasharray="3 3" />
            <XAxis dataKey={dimensionKey} tick={{ fill: 'var(--text-secondary)' }} />
            <YAxis tick={{ fill: 'var(--text-secondary)' }} />
            <Tooltip contentStyle={{ fontSize: '0.75rem' }} />
            <Legend />
            {measures.map((measure, index) => (
              <SeriesComponent
                key={measure}
                dataKey={measure}
                stroke={CHART_COLORS[index % CHART_COLORS.length]}
                fill={CHART_COLORS[index % CHART_COLORS.length]}
                strokeWidth={2}
                radius={variant === 'bar' ? 4 : undefined}
                type={variant === 'line' ? 'monotone' : undefined}
                dot={variant === 'line'}
              />
            ))}
          </ChartComponent>
        </ResponsiveContainer>
      </div>
    );
  };

  const renderScatterChart = () => {
    const xKey = x ?? (Array.isArray(measureFields) && measureFields.length > 0 ? measureFields[0] : null);
    const yCandidate = Array.isArray(measureFields) && measureFields.length > 1 ? measureFields[1] : measureFields[0];
    const yKey = typeof yCandidate === 'string' ? yCandidate : null;

    if (!xKey || !yKey) {
      return <ChartPlaceholder message="Scatter plots require two numeric fields." />;
    }

    const data = records
      .map((record) => {
        const xValue = toNumber(record[xKey]);
        const yValue = toNumber(record[yKey]);

        if (xValue === null || yValue === null) {
          return null;
        }

        return {
          [xKey]: xValue,
          [yKey]: yValue,
          label: record[groupBy ?? dimensionKey ?? 'label'],
        };
      })
      .filter((entry): entry is { [x: string]: number | string; label: string } => entry !== null);

    if (data.length === 0) {
      return <ChartPlaceholder message="Not enough numeric rows to render the scatter plot." />;
    }

    return (
      <div className="mt-4 h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <CartesianGrid stroke="rgba(148, 163, 184, 0.35)" />
            <XAxis dataKey={xKey} name={xKey} type="number" tick={{ fill: 'var(--text-secondary)' }} />
            <YAxis dataKey={yKey} name={yKey} type="number" tick={{ fill: 'var(--text-secondary)' }} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Legend />
            <Scatter data={data} fill={CHART_COLORS[0]} name={`${yKey} vs ${xKey}`} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  };

  const renderPieChart = () => {
    const dimension = dimensionKey ?? displayColumns[0];
    const measure = measureFields[0] ?? displayColumns.find((column) => column !== dimension) ?? null;

    if (!dimension || !measure) {
      return <ChartPlaceholder message="Pie charts require a label field and a numeric measure." />;
    }

    const data = records
      .map((record) => {
        const label = record[dimension];
        const value = toNumber(record[measure]);
        if (label === undefined || label === null || value === null) {
          return null;
        }
        return { name: String(label), value };
      })
      .filter((entry): entry is { name: string; value: number } => entry !== null);

    if (data.length === 0) {
      return <ChartPlaceholder message="Not enough numeric rows to render the pie chart." />;
    }

    return (
      <div className="mt-4 h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip />
            <Legend />
            <Pie data={data} dataKey="value" nameKey="name" outerRadius="80%">
              {data.map((entry, index) => (
                <Cell key={`${entry.name}-${index.toString()}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  };

  const chartElement = (() => {
    if (!result || !Array.isArray(result.rows) || result.rows.length === 0) {
      return <ChartPlaceholder message="No tabular data available to render a visualization." />;
    }

    switch (chartVariant) {
      case 'bar':
        return renderCategoricalChart('bar');
      case 'line':
        return renderCategoricalChart('line');
      case 'scatter':
        return renderScatterChart();
      case 'pie':
        return renderPieChart();
      default:
        return <ChartPlaceholder message="No chart preview available for this response." />;
    }
  })();

  return (
    <div className="space-y-2">
      {(title || chartType) && (
        <div className="flex items-center justify-between gap-2 text-xs text-[color:var(--text-muted)]">
          <span>{title || 'Chart'}</span>
          {chartType ? (
            <span className="inline-flex items-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-2 py-0.5 text-[10px] uppercase tracking-[0.08em]">
              {chartType}
            </span>
          ) : null}
        </div>
      )}
      <div className="rounded-xl border border-[color:var(--panel-border)]/70 bg-[color:var(--panel-bg)]/40 px-2 py-1">
        {chartElement}
      </div>
    </div>
  );
}
