'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
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
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { cn } from '@/lib/utils';
import { listSemanticModels } from '@/orchestration/semanticModels';
import type { SemanticModelRecord } from '@/orchestration/semanticModels/types';
import { fetchSemanticQueryMeta, runSemanticQuery } from '@/orchestration/semanticQuery';
import type {
  SemanticModelPayload,
  SemanticQueryMetaResponse,
  SemanticQueryRequestPayload,
  SemanticQueryResponse,
} from '@/orchestration/semanticQuery/types';

type FieldOption = {
  id: string;
  label: string;
  tableKey?: string;
  type?: string;
  kind: 'dimension' | 'measure' | 'metric' | 'segment';
};

type FilterDraft = {
  id: string;
  member: string;
  operator: string;
  values: string;
};

type ChartType = 'table' | 'bar' | 'line' | 'pie';

const FILTER_OPERATORS = [
  { value: 'equals', label: 'Equals' },
  { value: 'notequals', label: 'Not equals' },
  { value: 'contains', label: 'Contains' },
  { value: 'gt', label: 'Greater than' },
  { value: 'gte', label: 'Greater or equal' },
  { value: 'lt', label: 'Less than' },
  { value: 'lte', label: 'Less or equal' },
  { value: 'in', label: 'In list' },
  { value: 'notin', label: 'Not in list' },
  { value: 'set', label: 'Is set' },
  { value: 'notset', label: 'Is not set' },
];

const CHART_TYPES: Array<{ value: ChartType; label: string }> = [
  { value: 'table', label: 'Table only' },
  { value: 'bar', label: 'Bar chart' },
  { value: 'line', label: 'Line chart' },
  { value: 'pie', label: 'Pie chart' },
];

const CHART_COLORS = ['#0ea5e9', '#22c55e', '#f97316', '#ec4899', '#6366f1', '#eab308'];

export default function BiStudioPage() {
  const { selectedOrganizationId, selectedProjectId } = useWorkspaceScope();
  const [selectedModelId, setSelectedModelId] = useState('');
  const [selectedMeasures, setSelectedMeasures] = useState<string[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [selectedSegments, setSelectedSegments] = useState<string[]>([]);
  const [filters, setFilters] = useState<FilterDraft[]>([]);
  const [limit, setLimit] = useState(200);
  const [queryResult, setQueryResult] = useState<SemanticQueryResponse | null>(null);
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [chartX, setChartX] = useState('');
  const [chartY, setChartY] = useState('');

  const semanticModelsQuery = useQuery<SemanticModelRecord[]>({
    queryKey: ['semantic-models', selectedOrganizationId, selectedProjectId],
    queryFn: () =>
      listSemanticModels(selectedOrganizationId ?? '', selectedProjectId ?? undefined),
    enabled: Boolean(selectedOrganizationId),
  });

  const semanticMetaQuery = useQuery<SemanticQueryMetaResponse>({
    queryKey: ['semantic-model-meta', selectedOrganizationId, selectedModelId],
    queryFn: () => fetchSemanticQueryMeta(selectedModelId, selectedOrganizationId ?? ''),
    enabled: Boolean(selectedOrganizationId && selectedModelId),
  });

  const queryMutation = useMutation<SemanticQueryResponse, Error, SemanticQueryRequestPayload>({
    mutationFn: (payload) => runSemanticQuery(payload),
    onSuccess: (data) => {
      setQueryResult(data);
    },
  });

  useEffect(() => {
    if (semanticModelsQuery.data && semanticModelsQuery.data.length > 0 && !selectedModelId) {
      setSelectedModelId(semanticModelsQuery.data[0].id);
    }
  }, [semanticModelsQuery.data, selectedModelId]);

  useEffect(() => {
    setSelectedMeasures([]);
    setSelectedDimensions([]);
    setSelectedSegments([]);
    setFilters([]);
    setQueryResult(null);
  }, [selectedModelId]);

  const semanticModel = semanticMetaQuery.data?.semanticModel;
  const canRunQuery = selectedDimensions.length > 0 || selectedMeasures.length > 0;

  const { dimensionOptions, measureOptions, segmentOptions } = useMemo(() => {
    return buildFieldOptions(semanticModel);
  }, [semanticModel]);

  const filterFieldOptions = useMemo(() => {
    return [...dimensionOptions, ...measureOptions];
  }, [dimensionOptions, measureOptions]);

  const resultColumns = useMemo(() => {
    const rows = queryResult?.data ?? [];
    if (rows.length === 0) {
      return [];
    }
    return Object.keys(rows[0]);
  }, [queryResult]);

  useEffect(() => {
    if (resultColumns.length === 0) {
      setChartX('');
      setChartY('');
      return;
    }
    if (!chartX || !resultColumns.includes(chartX)) {
      setChartX(resultColumns[0]);
    }
    if (!chartY || !resultColumns.includes(chartY)) {
      const fallback = resultColumns.find((column) => column !== chartX) ?? resultColumns[0];
      setChartY(fallback);
    }
  }, [resultColumns, chartX, chartY]);

  const handleRunQuery = () => {
    if (!selectedOrganizationId || !selectedModelId || !canRunQuery) {
      return;
    }
    const payload: SemanticQueryRequestPayload = {
      organizationId: selectedOrganizationId,
      projectId: selectedProjectId ?? null,
      semanticModelId: selectedModelId,
      query: {
        measures: selectedMeasures,
        dimensions: selectedDimensions,
        segments: selectedSegments,
        filters: filters
          .filter((filter) => filter.member && filter.operator)
          .map((filter) => ({
            member: filter.member,
            operator: filter.operator,
            values: parseFilterValues(filter),
          })),
        limit: limit || undefined,
      },
    };
    queryMutation.mutate(payload);
  };

  if (!selectedOrganizationId) {
    return (
      <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-sm text-[color:var(--text-secondary)]">
        Select an organization to start building semantic queries.
      </div>
    );
  }

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[color:var(--text-muted)]">
          BI studio
        </p>
        <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
          Build dashboards from semantic queries
        </h1>
        <p className="max-w-3xl text-sm">
          Choose a semantic model, assemble dimensions and measures, and run lightweight BI queries for tables and
          charts. Results are powered by the semantic query endpoint and stay aligned to your model definitions.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <section className="space-y-6 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
          <div className="space-y-3">
            <Label htmlFor="semantic-model-picker">Semantic model</Label>
            <Select
              id="semantic-model-picker"
              value={selectedModelId}
              onChange={(event) => setSelectedModelId(event.target.value)}
              disabled={semanticModelsQuery.isLoading || semanticModelsQuery.isError}
              placeholder={semanticModelsQuery.isLoading ? 'Loading models...' : 'Select a model'}
            >
              {(semanticModelsQuery.data ?? []).map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </Select>
            {semanticModelsQuery.isError ? (
              <p className="text-xs text-rose-600">Unable to load semantic models.</p>
            ) : null}
          </div>

          {semanticMetaQuery.isLoading ? (
            <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
              Loading semantic model details...
            </div>
          ) : semanticMetaQuery.isError ? (
            <div className="rounded-2xl border border-dashed border-rose-300 bg-rose-100/40 p-4 text-sm text-rose-700">
              Could not load semantic model metadata.
            </div>
          ) : semanticModel ? (
            <ModelSummary semanticModel={semanticModel} />
          ) : (
            <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
              Select a semantic model to explore its schema.
            </div>
          )}
        </section>

        <section className="space-y-6">
          <div className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                  Query builder
                </p>
                <p className="text-sm text-[color:var(--text-secondary)]">
                  Pick measures and dimensions, then add filters or segments before running the query.
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                isLoading={queryMutation.isPending}
                disabled={!selectedModelId || queryMutation.isPending || !canRunQuery}
                onClick={handleRunQuery}
              >
                Run query
              </Button>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <FieldPicker
                title="Dimensions"
                options={dimensionOptions}
                selected={selectedDimensions}
                onToggle={(value) => toggleSelection(value, selectedDimensions, setSelectedDimensions)}
                emptyLabel="No dimensions available in this model."
              />
              <FieldPicker
                title="Measures"
                options={measureOptions}
                selected={selectedMeasures}
                onToggle={(value) => toggleSelection(value, selectedMeasures, setSelectedMeasures)}
                emptyLabel="No measures or metrics available."
              />
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <FieldPicker
                title="Segments"
                options={segmentOptions}
                selected={selectedSegments}
                onToggle={(value) => toggleSelection(value, selectedSegments, setSelectedSegments)}
                emptyLabel="No table filters configured."
              />
              <div className="space-y-3">
                <Label htmlFor="limit">Row limit</Label>
                <Input
                  id="limit"
                  type="number"
                  min={1}
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                />
              </div>
            </div>

            <div className="mt-6 space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Filters</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setFilters((current) => [
                      ...current,
                      { id: createId('filter'), member: '', operator: 'equals', values: '' },
                    ])
                  }
                >
                  Add filter
                </Button>
              </div>
              {filters.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
                  No filters applied yet.
                </div>
              ) : (
                <div className="space-y-3">
                  {filters.map((filter) => (
                    <div
                      key={filter.id}
                      className="grid gap-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 md:grid-cols-[2fr_1fr_2fr_auto]"
                    >
                      <Select
                        value={filter.member}
                        onChange={(event) =>
                          updateFilter(filters, setFilters, filter.id, { member: event.target.value })
                        }
                        placeholder="Select field"
                      >
                        {filterFieldOptions.map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.label}
                          </option>
                        ))}
                      </Select>
                      <Select
                        value={filter.operator}
                        onChange={(event) =>
                          updateFilter(filters, setFilters, filter.id, { operator: event.target.value })
                        }
                      >
                        {FILTER_OPERATORS.map((operator) => (
                          <option key={operator.value} value={operator.value}>
                            {operator.label}
                          </option>
                        ))}
                      </Select>
                      <Input
                        value={filter.values}
                        onChange={(event) =>
                          updateFilter(filters, setFilters, filter.id, { values: event.target.value })
                        }
                        placeholder="Comma-separated values"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setFilters((current) => current.filter((item) => item.id !== filter.id))}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                  Results
                </p>
                <p className="text-sm text-[color:var(--text-secondary)]">
                  Visualize the results as a chart or review raw table output.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Select value={chartType} onChange={(event) => setChartType(event.target.value as ChartType)}>
                  {CHART_TYPES.map((chart) => (
                    <option key={chart.value} value={chart.value}>
                      {chart.label}
                    </option>
                  ))}
                </Select>
                <Select
                  value={chartX}
                  onChange={(event) => setChartX(event.target.value)}
                  disabled={resultColumns.length === 0}
                  placeholder="X axis"
                >
                  {resultColumns.map((column) => (
                    <option key={column} value={column}>
                      X: {column}
                    </option>
                  ))}
                </Select>
                <Select
                  value={chartY}
                  onChange={(event) => setChartY(event.target.value)}
                  disabled={resultColumns.length === 0}
                  placeholder="Y axis"
                >
                  {resultColumns.map((column) => (
                    <option key={column} value={column}>
                      Y: {column}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            {queryMutation.isError ? (
              <div className="mt-4 rounded-2xl border border-rose-300 bg-rose-100/40 p-4 text-sm text-rose-700">
                {queryMutation.error?.message ?? 'Query failed.'}
              </div>
            ) : null}

            {queryResult && chartType !== 'table' ? (
              <ChartPreview
                chartType={chartType}
                data={queryResult.data ?? []}
                xKey={chartX}
                yKey={chartY}
              />
            ) : null}

            <ResultsTable rows={queryResult?.data ?? []} />
          </div>
        </section>
      </div>
    </div>
  );
}

function ModelSummary({ semanticModel }: { semanticModel: SemanticModelPayload }) {
  const tables = semanticModel.tables ?? {};
  const tableEntries = Object.entries(tables);
  const dimensionCount = tableEntries.reduce(
    (count, [, table]) => count + (table.dimensions?.length ?? 0),
    0,
  );
  const measureCount = tableEntries.reduce(
    (count, [, table]) => count + (table.measures?.length ?? 0),
    0,
  );
  const metricCount = Object.keys(semanticModel.metrics ?? {}).length;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <p className="text-lg font-semibold text-[color:var(--text-primary)]">
          {semanticModel.name ?? 'Semantic model'}
        </p>
        {semanticModel.description ? <p className="text-sm">{semanticModel.description}</p> : null}
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-[color:var(--text-muted)]">
        <Badge variant="secondary">{tableEntries.length} tables</Badge>
        <Badge variant="secondary">{dimensionCount} dimensions</Badge>
        <Badge variant="secondary">{measureCount} measures</Badge>
        <Badge variant="secondary">{metricCount} metrics</Badge>
      </div>
      <div className="space-y-3">
        {tableEntries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
            No tables defined in this model.
          </div>
        ) : (
          tableEntries.map(([tableKey, table]) => (
            <details
              key={tableKey}
              className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-3"
            >
              <summary className="cursor-pointer text-sm font-semibold text-[color:var(--text-primary)]">
                {tableKey} ({table.schema}.{table.name})
              </summary>
              <div className="mt-3 space-y-2 text-xs text-[color:var(--text-secondary)]">
                {table.description ? <p>{table.description}</p> : null}
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--text-muted)]">Dimensions</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(table.dimensions ?? []).map((dimension) => (
                      <span
                        key={`${tableKey}.${dimension.name}`}
                        className="rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-3 py-1"
                      >
                        {dimension.name}
                      </span>
                    ))}
                    {(table.dimensions ?? []).length === 0 ? <span>None</span> : null}
                  </div>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--text-muted)]">Measures</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(table.measures ?? []).map((measure) => (
                      <span
                        key={`${tableKey}.${measure.name}`}
                        className="rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-3 py-1"
                      >
                        {measure.name}
                      </span>
                    ))}
                    {(table.measures ?? []).length === 0 ? <span>None</span> : null}
                  </div>
                </div>
              </div>
            </details>
          ))
        )}
      </div>
    </div>
  );
}

function FieldPicker({
  title,
  options,
  selected,
  onToggle,
  emptyLabel,
}: {
  title: string;
  options: FieldOption[];
  selected: string[];
  onToggle: (value: string) => void;
  emptyLabel: string;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-[color:var(--text-primary)]">{title}</p>
      {options.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
          {emptyLabel}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {options.map((option) => {
            const active = selected.includes(option.id);
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onToggle(option.id)}
                aria-pressed={active}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs font-medium transition',
                  active
                    ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]'
                    : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-secondary)]',
                )}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ResultsTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="mt-4 rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
        Run a query to view results.
      </div>
    );
  }

  const columns = Object.keys(rows[0]);
  const previewRows = rows.slice(0, 50);

  return (
    <div className="mt-5 overflow-x-auto rounded-2xl border border-[color:var(--panel-border)]">
      <table className="min-w-full border-collapse text-left text-xs">
        <thead className="bg-[color:var(--panel-alt)] text-[color:var(--text-muted)]">
          <tr>
            {columns.map((column) => (
              <th key={column} className="whitespace-nowrap px-4 py-2 font-semibold">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {previewRows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-[color:var(--panel-border)]">
              {columns.map((column) => (
                <td key={`${rowIndex}-${column}`} className="px-4 py-2">
                  {formatCell(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > previewRows.length ? (
        <div className="border-t border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-2 text-xs text-[color:var(--text-muted)]">
          Showing {previewRows.length} of {rows.length} rows.
        </div>
      ) : null}
    </div>
  );
}

function ChartPreview({
  chartType,
  data,
  xKey,
  yKey,
}: {
  chartType: ChartType;
  data: Array<Record<string, unknown>>;
  xKey: string;
  yKey: string;
}) {
  if (!data || data.length === 0) {
    return null;
  }

  if (!xKey || !yKey) {
    return (
      <div className="mt-4 rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
        Choose chart axes to preview a visualization.
      </div>
    );
  }

  const chartData = data
    .map((row) => {
      const xValue = row[xKey];
      const yValue = toNumber(row[yKey]);
      if (xValue === undefined || xValue === null || yValue === null) {
        return null;
      }
      return {
        [xKey]: String(xValue),
        [yKey]: yValue,
      };
    })
    .filter((row): row is Record<string, string | number> => row !== null);

  if (chartData.length === 0) {
    return (
      <div className="mt-4 rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
        Not enough numeric data to render the chart.
      </div>
    );
  }

  if (chartType === 'pie') {
    return (
      <div className="mt-4 h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip />
            <Legend />
            <Pie data={chartData} dataKey={yKey} nameKey={xKey} outerRadius="80%">
              {chartData.map((entry, index) => (
                <Cell key={`${entry[xKey]}-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chartType === 'line') {
    return (
      <div className="mt-4 h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid stroke="rgba(148, 163, 184, 0.35)" strokeDasharray="3 3" />
            <XAxis dataKey={xKey} tick={{ fill: 'var(--text-secondary)' }} />
            <YAxis tick={{ fill: 'var(--text-secondary)' }} />
            <Tooltip />
            <Legend />
            <Line dataKey={yKey} stroke={CHART_COLORS[0]} strokeWidth={2} dot />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="mt-4 h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <CartesianGrid stroke="rgba(148, 163, 184, 0.35)" strokeDasharray="3 3" />
          <XAxis dataKey={xKey} tick={{ fill: 'var(--text-secondary)' }} />
          <YAxis tick={{ fill: 'var(--text-secondary)' }} />
          <Tooltip />
          <Legend />
          <Bar dataKey={yKey} fill={CHART_COLORS[0]} radius={4} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function buildFieldOptions(semanticModel?: SemanticModelPayload) {
  const dimensionOptions: FieldOption[] = [];
  const measureOptions: FieldOption[] = [];
  const segmentOptions: FieldOption[] = [];

  if (!semanticModel) {
    return { dimensionOptions, measureOptions, segmentOptions };
  }

  Object.entries(semanticModel.tables ?? {}).forEach(([tableKey, table]) => {
    (table.dimensions ?? []).forEach((dimension) => {
      dimensionOptions.push({
        id: `${tableKey}.${dimension.name}`,
        label: `${tableKey} / ${dimension.name}`,
        tableKey,
        type: dimension.type,
        kind: 'dimension',
      });
    });
    (table.measures ?? []).forEach((measure) => {
      measureOptions.push({
        id: `${tableKey}.${measure.name}`,
        label: `${tableKey} / ${measure.name}`,
        tableKey,
        type: measure.type,
        kind: 'measure',
      });
    });
    Object.entries(table.filters ?? {}).forEach(([filterKey]) => {
      segmentOptions.push({
        id: `${tableKey}.${filterKey}`,
        label: `${tableKey} / ${filterKey}`,
        tableKey,
        kind: 'segment',
      });
    });
  });

  Object.keys(semanticModel.metrics ?? {}).forEach((metricName) => {
    measureOptions.push({
      id: metricName,
      label: `metric / ${metricName}`,
      kind: 'metric',
    });
  });

  return { dimensionOptions, measureOptions, segmentOptions };
}

function toggleSelection(
  value: string,
  selected: string[],
  setSelected: (values: string[]) => void,
) {
  if (selected.includes(value)) {
    setSelected(selected.filter((item) => item !== value));
  } else {
    setSelected([...selected, value]);
  }
}

function updateFilter(
  filters: FilterDraft[],
  setFilters: (next: FilterDraft[]) => void,
  id: string,
  patch: Partial<FilterDraft>,
) {
  setFilters(
    filters.map((filter) => (filter.id === id ? { ...filter, ...patch } : filter)),
  );
}

function parseFilterValues(filter: FilterDraft): string[] | undefined {
  if (!filter.values) {
    return undefined;
  }
  const values = filter.values
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
  return values.length > 0 ? values : undefined;
}

function createId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) {
    return 'null';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}
