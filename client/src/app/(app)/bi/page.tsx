'use client';

import { useEffect, useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
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
  description?: string | null;
  aggregation?: string | null;
  kind: 'dimension' | 'measure' | 'metric' | 'segment';
};

type TableGroup = {
  tableKey: string;
  schema: string;
  name: string;
  description?: string | null;
  dimensions: FieldOption[];
  measures: FieldOption[];
  segments: FieldOption[];
};

type FilterDraft = {
  id: string;
  member: string;
  operator: string;
  values: string;
};

type OrderByDraft = {
  id: string;
  member: string;
  direction: 'asc' | 'desc';
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

const FILTER_LOGIC_OPTIONS = [
  { value: 'and', label: 'Match all' },
  { value: 'or', label: 'Match any' },
];

const ORDER_DIRECTIONS = [
  { value: 'asc', label: 'Ascending' },
  { value: 'desc', label: 'Descending' },
];

const AGGREGATION_OPTIONS = [
  { value: 'sum', label: 'Sum' },
  { value: 'avg', label: 'Average' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
  { value: 'count', label: 'Count' },
  { value: 'count_distinct', label: 'Count distinct' },
];

const TIME_GRAIN_OPTIONS = [
  { value: '', label: 'No grain' },
  { value: 'day', label: 'Day' },
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
  { value: 'quarter', label: 'Quarter' },
  { value: 'year', label: 'Year' },
];

const DATE_PRESETS = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'month_to_date', label: 'Month to date' },
  { value: 'year_to_date', label: 'Year to date' },
];

const VIZ_OPTIONS: Array<{ value: ChartType; label: string; icon: string; helper: string }> = [
  { value: 'table', label: 'Table', icon: 'Tbl', helper: 'Rows and columns' },
  { value: 'bar', label: 'Bar', icon: 'Bar', helper: 'Compare categories' },
  { value: 'line', label: 'Line', icon: 'Line', helper: 'Trends over time' },
  { value: 'pie', label: 'Pie', icon: 'Pie', helper: 'Share of total' },
];

const CHART_COLORS = ['#0ea5e9', '#22c55e', '#f97316', '#ec4899', '#6366f1', '#eab308'];

export default function BiStudioPage() {
  const { selectedOrganizationId, selectedProjectId } = useWorkspaceScope();
  const [selectedModelId, setSelectedModelId] = useState('');
  const [modelSearch, setModelSearch] = useState('');
  const [fieldSearch, setFieldSearch] = useState('');
  const [omniboxSearch, setOmniboxSearch] = useState('');
  const [omniboxIndex, setOmniboxIndex] = useState(0);
  const [recentModelIds, setRecentModelIds] = useState<string[]>([]);
  const [favoriteFields, setFavoriteFields] = useState<string[]>([]);
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null);
  const [fieldAliases, setFieldAliases] = useState<Record<string, string>>({});
  const [measureAggregations, setMeasureAggregations] = useState<Record<string, string>>({});
  const [selectedMeasures, setSelectedMeasures] = useState<string[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [selectedSegments, setSelectedSegments] = useState<string[]>([]);
  const [selectedTimeDimension, setSelectedTimeDimension] = useState('');
  const [timeGrain, setTimeGrain] = useState('');
  const [timeRangePreset, setTimeRangePreset] = useState('');
  const [timeRangeStart, setTimeRangeStart] = useState('');
  const [timeRangeEnd, setTimeRangeEnd] = useState('');
  const [filters, setFilters] = useState<FilterDraft[]>([]);
  const [filterLogic, setFilterLogic] = useState<'and' | 'or'>('and');
  const [limit, setLimit] = useState(200);
  const [orderBys, setOrderBys] = useState<OrderByDraft[]>([]);
  const [hasRunQuery, setHasRunQuery] = useState(false);
  const [queryResult, setQueryResult] = useState<SemanticQueryResponse | null>(null);
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [chartX, setChartX] = useState('');
  const [chartY, setChartY] = useState('');
  const [showSqlPreview, setShowSqlPreview] = useState(false);
  const [draggingField, setDraggingField] = useState<{
    id: string;
    kind: 'dimension' | 'measure';
  } | null>(null);

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
    if (!selectedModelId) {
      return;
    }
    setRecentModelIds((current) => {
      const next = [selectedModelId, ...current.filter((id) => id !== selectedModelId)];
      return next.slice(0, 4);
    });
  }, [selectedModelId]);

  useEffect(() => {
    setSelectedMeasures([]);
    setSelectedDimensions([]);
    setSelectedSegments([]);
    setSelectedTimeDimension('');
    setTimeGrain('');
    setTimeRangePreset('');
    setTimeRangeStart('');
    setTimeRangeEnd('');
    setFilters([]);
    setOrderBys([]);
    setQueryResult(null);
    setHasRunQuery(false);
    setFieldAliases({});
    setMeasureAggregations({});
    setFavoriteFields([]);
    setActiveFieldId(null);
    setFilterLogic('and');
    setShowSqlPreview(false);
  }, [selectedModelId]);

  const semanticModel = semanticMetaQuery.data?.semanticModel;
  const canRunQuery =
    selectedDimensions.length > 0 || selectedMeasures.length > 0 || Boolean(selectedTimeDimension);

  const { dimensionOptions, measureOptions, segmentOptions, metricOptions } = useMemo(() => {
    return buildFieldOptions(semanticModel);
  }, [semanticModel]);

  const tableGroups = useMemo(() => {
    return buildTableGroups(semanticModel);
  }, [semanticModel]);

  const filterFieldOptions = useMemo(() => {
    return [
      ...dimensionOptions,
      ...measureOptions.filter((option) => option.kind !== 'metric'),
    ];
  }, [dimensionOptions, measureOptions]);

  const timeDimensionOptions = useMemo(() => {
    return dimensionOptions.filter((option) => isTimeDimensionOption(option));
  }, [dimensionOptions]);

  const orderFieldOptions = useMemo(() => {
    return [...dimensionOptions, ...measureOptions];
  }, [dimensionOptions, measureOptions]);

  const fieldLookup = useMemo(() => {
    return new Map(
      [...dimensionOptions, ...measureOptions, ...segmentOptions].map((option) => [
        option.id,
        option,
      ]),
    );
  }, [dimensionOptions, measureOptions, segmentOptions]);

  const modelOptions = semanticModelsQuery.data ?? [];
  const selectedModel = modelOptions.find((model) => model.id === selectedModelId) ?? null;
  const filteredModels = useMemo(() => {
    if (!modelSearch.trim()) {
      return modelOptions;
    }
    const query = modelSearch.trim().toLowerCase();
    return modelOptions.filter((model) =>
      [model.name, model.description ?? ''].some((value) =>
        value.toLowerCase().includes(query),
      ),
    );
  }, [modelOptions, modelSearch]);

  const recentModels = useMemo(() => {
    return recentModelIds
      .map((id) => modelOptions.find((model) => model.id === id))
      .filter((model): model is SemanticModelRecord => Boolean(model));
  }, [recentModelIds, modelOptions]);

  const selectedFieldIds = useMemo(() => {
    const next = new Set([
      ...selectedDimensions,
      ...selectedMeasures,
      ...selectedSegments,
    ]);
    if (selectedTimeDimension) {
      next.add(selectedTimeDimension);
    }
    return next;
  }, [selectedDimensions, selectedMeasures, selectedSegments, selectedTimeDimension]);

  const omniboxResults = useMemo(() => {
    if (!omniboxSearch.trim()) {
      return [];
    }
    const query = omniboxSearch.trim().toLowerCase();
    return [...dimensionOptions, ...measureOptions]
      .filter((option) => option.label.toLowerCase().includes(query))
      .slice(0, 8);
  }, [dimensionOptions, measureOptions, omniboxSearch]);

  const activeField = activeFieldId ? fieldLookup.get(activeFieldId) : undefined;
  const selectedFieldCount =
    selectedDimensions.length +
    selectedMeasures.length +
    selectedSegments.length +
    (selectedTimeDimension ? 1 : 0);

  useEffect(() => {
    setOmniboxIndex(0);
  }, [omniboxResults.length]);

  useEffect(() => {
    if (!activeFieldId) {
      return;
    }
    const stillSelected =
      selectedDimensions.includes(activeFieldId) || selectedMeasures.includes(activeFieldId);
    if (!stillSelected) {
      setActiveFieldId(null);
    }
  }, [activeFieldId, selectedDimensions, selectedMeasures]);

  const resultColumns = useMemo(() => {
    const rows = queryResult?.data ?? [];
    if (rows.length === 0) {
      return [];
    }
    return Object.keys(rows[0]);
  }, [queryResult]);
  const resultCount = queryResult?.data?.length ?? 0;

  useEffect(() => {
    if (resultColumns.length === 0) {
      setChartX('');
      setChartY('');
      return;
    }
    const timeAlias = selectedTimeDimension
      ? buildTimeDimensionAlias(selectedTimeDimension, timeGrain)
      : '';
    const preferredX =
      (timeAlias && resultColumns.includes(timeAlias) ? timeAlias : null) ??
      selectedDimensions.find((dimension) => resultColumns.includes(dimension)) ??
      resultColumns[0];
    const resolvedX = resultColumns.includes(chartX) ? chartX : preferredX;
    const preferredY =
      selectedMeasures.find((measure) => resultColumns.includes(measure)) ??
      resultColumns.find((column) => column !== resolvedX) ??
      resultColumns[0];
    const resolvedY = resultColumns.includes(chartY) ? chartY : preferredY;
    if (!chartX || !resultColumns.includes(chartX)) {
      setChartX(resolvedX);
    }
    if (!chartY || !resultColumns.includes(chartY)) {
      setChartY(resolvedY);
    }
  }, [
    resultColumns,
    chartX,
    chartY,
    selectedDimensions,
    selectedMeasures,
    selectedTimeDimension,
    timeGrain,
  ]);

  const handleRunQuery = () => {
    if (!selectedOrganizationId || !selectedModelId || !canRunQuery) {
      return;
    }
    setHasRunQuery(true);
    const timeRange = buildTimeRange({
      preset: timeRangePreset,
      start: timeRangeStart,
      end: timeRangeEnd,
    });
    const timeDimensions = selectedTimeDimension
      ? [
          {
            dimension: selectedTimeDimension,
            granularity: timeGrain || undefined,
            dateRange: timeRange,
          },
        ]
      : undefined;
    const order = buildOrderPayload(orderBys);
    const payload: SemanticQueryRequestPayload = {
      organizationId: selectedOrganizationId,
      projectId: (selectedProjectId === '' ? null : selectedProjectId) ?? null,
      semanticModelId: selectedModelId,
      query: {
        measures: selectedMeasures,
        dimensions: selectedDimensions,
        timeDimensions,
        segments: selectedSegments,
        filters: filters
          .filter((filter) => filter.member && filter.operator)
          .map((filter) => ({
            member: filter.member,
            operator: filter.operator,
            values: parseFilterValues(filter),
          })),
        order,
        limit: limit || undefined,
      },
    };
    queryMutation.mutate(payload);
  };

  const handleSelectModel = (modelId: string) => {
    setSelectedModelId(modelId);
    setModelSearch('');
  };

  const handleToggleFavorite = (fieldId: string) => {
    setFavoriteFields((current) =>
      current.includes(fieldId)
        ? current.filter((id) => id !== fieldId)
        : [...current, fieldId],
    );
  };

  const handleAddField = (field: FieldOption) => {
    if (field.kind === 'dimension') {
      addSelection(field.id, selectedDimensions, setSelectedDimensions);
      return;
    }
    if (field.kind === 'segment') {
      toggleSelection(field.id, selectedSegments, setSelectedSegments);
      return;
    }
    addSelection(field.id, selectedMeasures, setSelectedMeasures);
  };

  const handleOmniboxKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (omniboxResults.length === 0) {
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOmniboxIndex((current) => Math.min(current + 1, omniboxResults.length - 1));
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setOmniboxIndex((current) => Math.max(current - 1, 0));
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      const selection = omniboxResults[omniboxIndex] ?? omniboxResults[0];
      if (selection) {
        handleAddField(selection);
        setOmniboxSearch('');
      }
    }
  };

  const handleExportCsv = () => {
    if (!queryResult?.data || queryResult.data.length === 0) {
      return;
    }
    const columns = Object.keys(queryResult.data[0]);
    const csvRows = [
      columns.join(','),
      ...queryResult.data.map((row) =>
        columns.map((column) => toCsvValue(row[column])).join(','),
      ),
    ];
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `semantic-query-${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!selectedOrganizationId) {
    return (
      <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-sm text-[color:var(--text-secondary)]">
        Select an organization to start building semantic queries.
      </div>
    );
  }

  return (
    <div className="relative space-y-8 text-[color:var(--text-secondary)]">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-28 right-6 h-72 w-72 rounded-full bg-[color:var(--accent-soft)] opacity-45 blur-3xl" />
        <div className="absolute bottom-0 left-0 h-72 w-72 rounded-full bg-[color:var(--panel-alt)] opacity-70 blur-3xl" />
      </div>
      <section className="bi-fade-up rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-[color:var(--text-muted)]">
              BI studio
            </p>
            <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
              Visual query canvas
            </h1>
            <p className="max-w-3xl text-sm">
              Assemble semantic fields, shape visuals, and publish lightweight dashboards.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                Active model
              </p>
              <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                {selectedModel?.name ?? 'Select a model'}
              </p>
              {selectedModel?.description ? (
                <p className="text-xs text-[color:var(--text-muted)]">
                  {selectedModel.description}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{selectedFieldCount} fields</Badge>
              <Badge variant="secondary">{filters.length} filters</Badge>
              <Badge variant="secondary">{selectedSegments.length} segments</Badge>
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
        </div>
      </section>

      <div className="grid gap-8 xl:grid-cols-12">
        <aside className="bi-fade-up bi-stagger-1 space-y-6 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 shadow-soft xl:col-span-3">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              Data
            </p>
            <p className="text-sm">Models, tables, and fields.</p>
          </div>

          <div className="space-y-3">
            <Label htmlFor="model-search">Model switcher</Label>
            <Input
              id="model-search"
              value={modelSearch}
              onChange={(event) => setModelSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && filteredModels[0]) {
                  event.preventDefault();
                  handleSelectModel(filteredModels[0].id);
                }
              }}
              placeholder={semanticModelsQuery.isLoading ? 'Loading models...' : 'Search models'}
              disabled={semanticModelsQuery.isLoading}
            />
            <div className="max-h-72 space-y-1 overflow-y-auto rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-2">
              {semanticModelsQuery.isLoading ? (
                <p className="px-3 py-2 text-xs text-[color:var(--text-muted)]">
                  Loading semantic models...
                </p>
              ) : filteredModels.length === 0 ? (
                <p className="px-3 py-2 text-xs text-[color:var(--text-muted)]">
                  No models match this search.
                </p>
              ) : (
                filteredModels.map((model) => (
                  <button
                    key={model.id}
                    type="button"
                    onClick={() => handleSelectModel(model.id)}
                    className={cn(
                      'w-full rounded-xl border px-3 py-2 text-left text-sm transition',
                      model.id === selectedModelId
                        ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]'
                        : 'border-transparent hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-bg)]',
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[color:var(--text-primary)]">
                        {model.name}
                      </span>
                      {model.id === selectedModelId ? (
                        <Badge variant="secondary">Active</Badge>
                      ) : null}
                    </div>
                    {model.description ? (
                      <p className="mt-1 text-xs text-[color:var(--text-muted)]">
                        {model.description}
                      </p>
                    ) : null}
                  </button>
                ))
              )}
            </div>
            {semanticModelsQuery.isError ? (
              <p className="text-xs text-rose-600">Unable to load semantic models.</p>
            ) : null}
            {recentModels.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
                  Recent
                </p>
                <div className="flex flex-wrap gap-2">
                  {recentModels.map((model) => (
                    <button
                      key={model.id}
                      type="button"
                      onClick={() => handleSelectModel(model.id)}
                      className={cn(
                        'rounded-full border px-3 py-1 text-xs font-medium transition',
                        model.id === selectedModelId
                          ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]'
                          : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-secondary)]',
                      )}
                    >
                      {model.name}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                  Fields
                </p>
                <p className="text-sm">Dimensions, measures, and segments.</p>
              </div>
              {semanticModel ? <Badge variant="secondary">{tableGroups.length} tables</Badge> : null}
            </div>
            <Input
              value={fieldSearch}
              onChange={(event) => setFieldSearch(event.target.value)}
              placeholder="Search fields or tables"
              disabled={!semanticModel || semanticMetaQuery.isLoading}
            />
            {semanticMetaQuery.isLoading ? (
              <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
                Loading semantic model details...
              </div>
            ) : semanticMetaQuery.isError ? (
              <div className="rounded-2xl border border-dashed border-rose-300 bg-rose-100/40 p-4 text-sm text-rose-700">
                Could not load semantic model metadata.
              </div>
            ) : semanticModel ? (
              <SemanticExplorer
                semanticModel={semanticModel}
                tableGroups={tableGroups}
                metricOptions={metricOptions}
                searchTerm={fieldSearch}
                favorites={favoriteFields}
                selectedFields={selectedFieldIds}
                fieldLookup={fieldLookup}
                onToggleFavorite={handleToggleFavorite}
                onAddField={handleAddField}
                onToggleSegment={(segmentId) =>
                  toggleSelection(segmentId, selectedSegments, setSelectedSegments)
                }
              />
            ) : (
              <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
                Select a semantic model to explore its schema.
              </div>
            )}
          </div>
        </aside>

        <main className="space-y-6 xl:col-span-6">
          <section className="bi-fade-up bi-stagger-2 space-y-6 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                Query canvas
              </p>
              <p className="text-sm text-[color:var(--text-secondary)]">
                Drag fields from the data pane or use the omnibox to build your query.
              </p>
            </div>
            <Badge variant="secondary">{selectedFieldCount} fields selected</Badge>
          </div>

          <div className="space-y-2">
            <Label htmlFor="field-omnibox">Field omnibox</Label>
            <Input
              id="field-omnibox"
              value={omniboxSearch}
              onChange={(event) => setOmniboxSearch(event.target.value)}
              onKeyDown={handleOmniboxKeyDown}
              placeholder="Search dimensions, measures, metrics"
            />
            <p className="text-xs text-[color:var(--text-muted)]">
              Use arrows to navigate and Enter to add a field.
            </p>
            {omniboxSearch ? (
              <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-2">
                {omniboxResults.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-[color:var(--text-muted)]">
                    No matching fields.
                  </p>
                ) : (
                  <div className="space-y-1">
                    {omniboxResults.map((option, index) => (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => {
                          handleAddField(option);
                          setOmniboxSearch('');
                        }}
                        className={cn(
                          'flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition',
                          index === omniboxIndex
                            ? 'bg-[color:var(--panel-bg)] text-[color:var(--text-primary)]'
                            : 'text-[color:var(--text-secondary)] hover:bg-[color:var(--panel-bg)]',
                        )}
                      >
                        <span className="flex items-center gap-2">
                          <span className="rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-2 py-0.5 text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
                            {option.kind}
                          </span>
                          {option.label}
                        </span>
                        {option.type ? (
                          <span className="text-xs text-[color:var(--text-muted)]">
                            {option.type}
                          </span>
                        ) : null}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </div>

          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                Selected fields
              </p>
              <span className="text-xs text-[color:var(--text-muted)]">
                {selectedFieldCount} selected
              </span>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <SelectedFieldGroup
                title="Dimensions"
                selected={selectedDimensions}
                kind="dimension"
                activeFieldId={activeFieldId}
                fieldLookup={fieldLookup}
                aliases={fieldAliases}
                draggingField={draggingField}
                onActivate={setActiveFieldId}
                onRemove={(id) =>
                  setSelectedDimensions((current) => current.filter((item) => item !== id))
                }
                onDragStart={(id) => setDraggingField({ id, kind: 'dimension' })}
                onDragEnd={() => setDraggingField(null)}
                onDrop={(targetId) => {
                  if (!draggingField || draggingField.kind !== 'dimension') {
                    return;
                  }
                  setSelectedDimensions((current) =>
                    reorderList(current, draggingField.id, targetId),
                  );
                  setDraggingField(null);
                }}
              />
              <SelectedFieldGroup
                title="Measures"
                selected={selectedMeasures}
                kind="measure"
                activeFieldId={activeFieldId}
                fieldLookup={fieldLookup}
                aliases={fieldAliases}
                draggingField={draggingField}
                onActivate={setActiveFieldId}
                onRemove={(id) =>
                  setSelectedMeasures((current) => current.filter((item) => item !== id))
                }
                onDragStart={(id) => setDraggingField({ id, kind: 'measure' })}
                onDragEnd={() => setDraggingField(null)}
                onDrop={(targetId) => {
                  if (!draggingField || draggingField.kind !== 'measure') {
                    return;
                  }
                  setSelectedMeasures((current) =>
                    reorderList(current, draggingField.id, targetId),
                  );
                  setDraggingField(null);
                }}
              />
            </div>

            {activeField ? (
              <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                      Field settings
                    </p>
                    <p className="text-xs text-[color:var(--text-muted)]">
                      {activeField.label}
                    </p>
                  </div>
                  <Badge variant="secondary">{activeField.kind}</Badge>
                </div>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="field-alias">Alias</Label>
                    <Input
                      id="field-alias"
                      value={fieldAliases[activeField.id] ?? ''}
                      onChange={(event) =>
                        setFieldAliases((current) => ({
                          ...current,
                          [activeField.id]: event.target.value,
                        }))
                      }
                      placeholder="Add a display name"
                    />
                  </div>
                  {activeField.kind === 'measure' || activeField.kind === 'metric' ? (
                    <div className="space-y-2">
                      <Label htmlFor="field-aggregation">Aggregation</Label>
                      <Select
                        id="field-aggregation"
                        value={
                          measureAggregations[activeField.id] ??
                          activeField.aggregation ??
                          'sum'
                        }
                        onChange={(event) =>
                          setMeasureAggregations((current) => ({
                            ...current,
                            [activeField.id]: event.target.value,
                          }))
                        }
                      >
                        {AGGREGATION_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </Select>
                    </div>
                  ) : null}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={
                      activeField.kind === 'dimension'
                        ? selectedDimensions.indexOf(activeField.id) <= 0
                        : selectedMeasures.indexOf(activeField.id) <= 0
                    }
                    onClick={() => {
                      if (activeField.kind === 'dimension') {
                        setSelectedDimensions((current) =>
                          moveItem(current, activeField.id, -1),
                        );
                      } else {
                        setSelectedMeasures((current) =>
                          moveItem(current, activeField.id, -1),
                        );
                      }
                    }}
                  >
                    Move up
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={
                      activeField.kind === 'dimension'
                        ? selectedDimensions.indexOf(activeField.id) ===
                          selectedDimensions.length - 1
                        : selectedMeasures.indexOf(activeField.id) ===
                          selectedMeasures.length - 1
                    }
                    onClick={() => {
                      if (activeField.kind === 'dimension') {
                        setSelectedDimensions((current) =>
                          moveItem(current, activeField.id, 1),
                        );
                      } else {
                        setSelectedMeasures((current) =>
                          moveItem(current, activeField.id, 1),
                        );
                      }
                    }}
                  >
                    Move down
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => setActiveFieldId(null)}
                  >
                    Close
                  </Button>
                </div>
                <p className="mt-3 text-xs text-[color:var(--text-muted)]">
                  Drag chips to reorder or use move actions for precise control.
                </p>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
                Select a field chip to rename or adjust aggregation.
              </div>
            )}
          </div>

        </section>

        <section className="bi-fade-up bi-stagger-3 space-y-6 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                Canvas preview
              </p>
              <p className="text-sm text-[color:var(--text-secondary)]">
                Review the visualization and the data backing it.
              </p>
            </div>
            <Badge variant="secondary">{resultCount} rows</Badge>
          </div>

          {queryMutation.isError ? (
            <div className="rounded-2xl border border-rose-300 bg-rose-100/40 p-4 text-sm text-rose-700">
              {queryMutation.error?.message ?? 'Query failed.'}
            </div>
          ) : null}

          {queryMutation.isPending ? (
            <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
              Running query...
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

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              {chartType === 'table' ? 'Table view' : 'Data preview'}
            </p>
            <ResultsTable
              rows={queryResult?.data ?? []}
              hasRunQuery={hasRunQuery}
              isLoading={queryMutation.isPending}
            />
          </div>
        </section>
      </main>

      <aside className="bi-fade-up bi-stagger-4 space-y-6 xl:col-span-3">
        <section className="space-y-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 shadow-soft">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              Visualization
            </p>
            <p className="text-sm text-[color:var(--text-secondary)]">
              Pick a chart and map the axes.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {VIZ_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setChartType(option.value)}
                className={cn(
                  'flex items-center justify-between rounded-2xl border px-3 py-3 text-left text-sm transition',
                  chartType === option.value
                    ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]'
                    : 'border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] text-[color:var(--text-secondary)] hover:bg-[color:var(--panel-bg)]',
                )}
              >
                <span className="flex items-center gap-2">
                  <span className="rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-2 py-0.5 text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
                    {option.icon}
                  </span>
                  <span className="font-medium">{option.label}</span>
                </span>
                <span className="text-xs text-[color:var(--text-muted)]">{option.helper}</span>
              </button>
            ))}
          </div>
          <div className="grid gap-3">
            <Select
              value={chartX}
              onChange={(event) => setChartX(event.target.value)}
              disabled={resultColumns.length === 0 || chartType === 'table'}
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
              disabled={resultColumns.length === 0 || chartType === 'table'}
              placeholder="Y axis"
            >
              {resultColumns.map((column) => (
                <option key={column} value={column}>
                  Y: {column}
                </option>
              ))}
            </Select>
          </div>
        </section>

        <section className="space-y-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 shadow-soft">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              Order by
            </p>
            <p className="text-sm text-[color:var(--text-secondary)]">
              Sort results for ranking and leaderboards.
            </p>
          </div>
          {orderBys.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
              No ordering applied.
            </div>
          ) : (
            <div className="space-y-3">
              {orderBys.map((orderBy) => (
                <div
                  key={orderBy.id}
                  className="flex flex-wrap items-center gap-2 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-3"
                >
                  <Select
                    value={orderBy.member}
                    onChange={(event) => {
                      const member = event.target.value;
                      const field = fieldLookup.get(member);
                      const direction =
                        field?.kind === 'dimension'
                          ? 'asc'
                          : field
                            ? 'desc'
                            : orderBy.direction;
                      setOrderBys((current) =>
                        current.map((item) =>
                          item.id === orderBy.id ? { ...item, member, direction } : item,
                        ),
                      );
                    }}
                    placeholder="Field"
                    className="min-w-[180px]"
                    disabled={orderFieldOptions.length === 0}
                  >
                    {orderFieldOptions.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                  <Select
                    value={orderBy.direction}
                    onChange={(event) =>
                      setOrderBys((current) =>
                        current.map((item) =>
                          item.id === orderBy.id
                            ? {
                                ...item,
                                direction: event.target.value as 'asc' | 'desc',
                              }
                            : item,
                        ),
                      )
                    }
                    className="min-w-[140px]"
                  >
                    {ORDER_DIRECTIONS.map((direction) => (
                      <option key={direction.value} value={direction.value}>
                        {direction.label}
                      </option>
                    ))}
                  </Select>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setOrderBys((current) =>
                        current.filter((item) => item.id !== orderBy.id),
                      )
                    }
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              setOrderBys((current) => [
                ...current,
                { id: createId('order'), member: '', direction: 'desc' },
              ])
            }
            disabled={orderFieldOptions.length === 0}
          >
            Add order
          </Button>
        </section>

        <section className="space-y-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 shadow-soft">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              Filters
            </p>
            <p className="text-sm text-[color:var(--text-secondary)]">
              Segment the data and apply ad-hoc rules.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                Time dimension
              </p>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSelectedTimeDimension('');
                  setTimeGrain('');
                  setTimeRangePreset('');
                  setTimeRangeStart('');
                  setTimeRangeEnd('');
                }}
                disabled={
                  !selectedTimeDimension &&
                  !timeRangePreset &&
                  !timeRangeStart &&
                  !timeRangeEnd
                }
              >
                Clear
              </Button>
            </div>
            <Select
              value={selectedTimeDimension}
              onChange={(event) => setSelectedTimeDimension(event.target.value)}
              placeholder="Select time field"
              disabled={timeDimensionOptions.length === 0}
            >
              {timeDimensionOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </Select>
            <div className="grid gap-2 sm:grid-cols-2">
              <Select
                value={timeGrain}
                onChange={(event) => setTimeGrain(event.target.value)}
                disabled={!selectedTimeDimension}
              >
                {TIME_GRAIN_OPTIONS.map((option) => (
                  <option key={option.value || 'none'} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
              <Select
                value={timeRangePreset}
                onChange={(event) => {
                  const value = event.target.value;
                  setTimeRangePreset(value);
                  if (value) {
                    setTimeRangeStart('');
                    setTimeRangeEnd('');
                  }
                }}
                placeholder="Preset range"
                disabled={!selectedTimeDimension}
              >
                {DATE_PRESETS.map((preset) => (
                  <option key={preset.value} value={preset.value}>
                    {preset.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <Input
                type="date"
                value={timeRangeStart}
                onChange={(event) => {
                  setTimeRangeStart(event.target.value);
                  if (event.target.value) {
                    setTimeRangePreset('');
                  }
                }}
                placeholder="Start"
                disabled={!selectedTimeDimension || Boolean(timeRangePreset)}
              />
              <Input
                type="date"
                value={timeRangeEnd}
                onChange={(event) => {
                  setTimeRangeEnd(event.target.value);
                  if (event.target.value) {
                    setTimeRangePreset('');
                  }
                }}
                placeholder="End"
                disabled={!selectedTimeDimension || Boolean(timeRangePreset)}
              />
            </div>
            <p className="text-xs text-[color:var(--text-muted)]">
              Choose a grain to group time series and a date range for filtering.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-[color:var(--text-primary)]">Segments</p>
              <Badge variant="secondary">{selectedSegments.length} active</Badge>
            </div>
            {segmentOptions.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
                No segments saved in this model.
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {segmentOptions.map((segment) => {
                  const active = selectedSegments.includes(segment.id);
                  return (
                    <button
                      key={segment.id}
                      type="button"
                      onClick={() =>
                        toggleSelection(segment.id, selectedSegments, setSelectedSegments)
                      }
                      aria-pressed={active}
                      className={cn(
                        'rounded-full border px-3 py-1 text-xs font-medium transition',
                        active
                          ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]'
                          : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-secondary)]',
                      )}
                    >
                      {segment.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                Filter rules
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={filterLogic}
                  onChange={(event) => setFilterLogic(event.target.value as 'and' | 'or')}
                >
                  {FILTER_LOGIC_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
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
            </div>
            {filters.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
                No filters applied yet.
              </div>
            ) : (
              <div className="space-y-3">
                {filters.map((filter) => {
                  const field = fieldLookup.get(filter.member);
                  const inputType = getFilterInputType(field?.type);
                  const isPresetMatch = DATE_PRESETS.some(
                    (preset) => preset.value === filter.values,
                  );
                  const operatorNeedsValue = !['set', 'notset'].includes(filter.operator);
                  return (
                    <div
                      key={filter.id}
                      className="flex flex-wrap items-center gap-2 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-3"
                    >
                      <Select
                        value={filter.member}
                        onChange={(event) =>
                          updateFilter(filters, setFilters, filter.id, {
                            member: event.target.value,
                          })
                        }
                        placeholder="Field"
                        className="min-w-[180px]"
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
                          updateFilter(filters, setFilters, filter.id, {
                            operator: event.target.value,
                          })
                        }
                        className="min-w-[140px]"
                      >
                        {FILTER_OPERATORS.map((operator) => (
                          <option key={operator.value} value={operator.value}>
                            {operator.label}
                          </option>
                        ))}
                      </Select>
                      {inputType === 'date' ? (
                        <>
                          <Select
                            value={isPresetMatch ? filter.values : ''}
                            onChange={(event) =>
                              updateFilter(filters, setFilters, filter.id, {
                                values: event.target.value,
                              })
                            }
                            placeholder="Preset"
                            className="min-w-[160px]"
                            disabled={!operatorNeedsValue}
                          >
                            {DATE_PRESETS.map((preset) => (
                              <option key={preset.value} value={preset.value}>
                                {preset.label}
                              </option>
                            ))}
                          </Select>
                          <Input
                            value={isPresetMatch ? '' : filter.values}
                            onChange={(event) =>
                              updateFilter(filters, setFilters, filter.id, {
                                values: event.target.value,
                              })
                            }
                            placeholder="YYYY-MM-DD or range"
                            disabled={!operatorNeedsValue}
                            className="min-w-[200px]"
                          />
                        </>
                      ) : (
                        <Input
                          value={filter.values}
                          onChange={(event) =>
                            updateFilter(filters, setFilters, filter.id, {
                              values: event.target.value,
                            })
                          }
                          placeholder={
                            inputType === 'number'
                              ? 'Value or range (e.g. 10, 200)'
                              : 'Comma-separated values'
                          }
                          disabled={!operatorNeedsValue}
                          className="min-w-[200px]"
                        />
                      )}
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setFilters((current) =>
                            current.filter((item) => item.id !== filter.id),
                          )
                        }
                      >
                        Remove
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="limit">Row limit</Label>
            <Input
              id="limit"
              type="number"
              min={1}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
            />
            <p className="text-xs text-[color:var(--text-muted)]">
              Smart default keeps results fast while previewing.
            </p>
          </div>
        </section>

        <section className="space-y-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 shadow-soft">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              Actions
            </p>
            <p className="text-sm text-[color:var(--text-secondary)]">
              Export data or preview SQL before saving.
            </p>
          </div>
          <div className="grid gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleExportCsv}
              disabled={!queryResult?.data || queryResult.data.length === 0}
            >
              Export CSV
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowSqlPreview((current) => !current)}
              disabled={!selectedModelId}
            >
              SQL preview
            </Button>
            <div className="grid gap-2 sm:grid-cols-2">
              <Button type="button" variant="secondary" size="sm" disabled>
                Save chart
              </Button>
              <Button type="button" variant="secondary" size="sm" disabled>
                Save dashboard
              </Button>
            </div>
          </div>

          {showSqlPreview ? (
            <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-xs text-[color:var(--text-secondary)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
                SQL preview
              </p>
              <pre className="mt-3 whitespace-pre-wrap text-xs">
                {buildSqlPreview({
                  semanticModelName: semanticModel?.name ?? null,
                  selectedDimensions,
                  selectedMeasures,
                  selectedSegments,
                  selectedTimeDimension,
                  timeGrain,
                  timeRangePreset,
                  timeRangeStart,
                  timeRangeEnd,
                  orderBys,
                  filters,
                  limit,
                  filterLogic,
                })}
              </pre>
              <p className="mt-2 text-xs text-[color:var(--text-muted)]">
                Preview reflects selected fields; generated SQL may vary by connector.
              </p>
            </div>
          ) : null}
        </section>
      </aside>
    </div>
    <style jsx global>{`
      @keyframes biFadeUp {
        from {
          opacity: 0;
          transform: translateY(12px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }
      .bi-fade-up {
        animation: biFadeUp 0.7s ease both;
      }
      .bi-stagger-1 {
        animation-delay: 0.04s;
      }
      .bi-stagger-2 {
        animation-delay: 0.08s;
      }
      .bi-stagger-3 {
        animation-delay: 0.12s;
      }
      .bi-stagger-4 {
        animation-delay: 0.16s;
      }
      @media (prefers-reduced-motion: reduce) {
        .bi-fade-up {
          animation: none;
        }
      }
    `}</style>
  </div>
  );
}

function SemanticExplorer({
  semanticModel,
  tableGroups,
  metricOptions,
  searchTerm,
  favorites,
  selectedFields,
  fieldLookup,
  onToggleFavorite,
  onAddField,
  onToggleSegment,
}: {
  semanticModel: SemanticModelPayload;
  tableGroups: TableGroup[];
  metricOptions: FieldOption[];
  searchTerm: string;
  favorites: string[];
  selectedFields: Set<string>;
  fieldLookup: Map<string, FieldOption>;
  onToggleFavorite: (fieldId: string) => void;
  onAddField: (field: FieldOption) => void;
  onToggleSegment: (segmentId: string) => void;
}) {
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const matchesSearch = (value: string) => {
    if (!normalizedSearch) {
      return true;
    }
    return value.toLowerCase().includes(normalizedSearch);
  };

  const pinnedFields = favorites
    .map((id) => fieldLookup.get(id))
    .filter((field): field is FieldOption => Boolean(field))
    .filter((field) => matchesSearch(field.label));

  const visibleMetrics = metricOptions.filter((metric) => matchesSearch(metric.label));

  const filteredTables = tableGroups
    .map((group) => {
      const tableMatch =
        matchesSearch(group.tableKey) ||
        matchesSearch(group.name) ||
        matchesSearch(group.schema);
      const dimensions = tableMatch
        ? group.dimensions
        : group.dimensions.filter((field) => matchesSearch(field.label));
      const measures = tableMatch
        ? group.measures
        : group.measures.filter((field) => matchesSearch(field.label));
      const segments = tableMatch
        ? group.segments
        : group.segments.filter((field) => matchesSearch(field.label));
      if (!tableMatch && dimensions.length === 0 && measures.length === 0 && segments.length === 0) {
        return null;
      }
      return { ...group, dimensions, measures, segments };
    })
    .filter((group): group is TableGroup => Boolean(group));

  const dimensionCount = tableGroups.reduce(
    (count, table) => count + table.dimensions.length,
    0,
  );
  const measureCount = tableGroups.reduce(
    (count, table) => count + table.measures.length,
    0,
  );
  const segmentCount = tableGroups.reduce(
    (count, table) => count + table.segments.length,
    0,
  );

  const renderFieldRow = (field: FieldOption) => {
    const isSelected = selectedFields.has(field.id);
    const isPinned = favorites.includes(field.id);
    const actionLabel =
      field.kind === 'segment' ? (isSelected ? 'Disable' : 'Enable') : isSelected ? 'Added' : 'Add';
    const actionVariant = isSelected ? 'secondary' : 'outline';
    return (
      <div
        key={field.id}
        className={cn(
          'flex flex-wrap items-center justify-between gap-3 rounded-2xl border px-3 py-2 text-sm',
          isSelected
            ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)]'
            : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]',
        )}
        title={field.description ?? field.label}
      >
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
            {getFieldKindLabel(field.kind)}
          </span>
          <div>
            <p className="text-sm font-medium text-[color:var(--text-primary)]">{field.label}</p>
            {field.description ? (
              <p className="text-xs text-[color:var(--text-muted)]">{field.description}</p>
            ) : field.type ? (
              <p className="text-xs text-[color:var(--text-muted)]">{field.type}</p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onToggleFavorite(field.id)}
            className={cn(
              'rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition',
              isPinned
                ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]'
                : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-muted)]',
            )}
          >
            {isPinned ? 'Pinned' : 'Pin'}
          </button>
          <Button
            type="button"
            variant={actionVariant}
            size="sm"
            className="h-7 px-2 text-xs"
            disabled={isSelected && field.kind !== 'segment'}
            onClick={() =>
              field.kind === 'segment' ? onToggleSegment(field.id) : onAddField(field)
            }
          >
            {actionLabel}
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
        <p className="text-lg font-semibold text-[color:var(--text-primary)]">
          {semanticModel.name ?? 'Semantic model'}
        </p>
        {semanticModel.description ? (
          <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
            {semanticModel.description}
          </p>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-[color:var(--text-muted)]">
          <Badge variant="secondary">{tableGroups.length} tables</Badge>
          <Badge variant="secondary">{dimensionCount} dimensions</Badge>
          <Badge variant="secondary">{measureCount} measures</Badge>
          <Badge variant="secondary">{metricOptions.length} metrics</Badge>
          <Badge variant="secondary">{segmentCount} segments</Badge>
        </div>
      </div>

      {pinnedFields.length > 0 ? (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
            Pinned fields
          </p>
          <div className="space-y-2">{pinnedFields.map((field) => renderFieldRow(field))}</div>
        </div>
      ) : null}

      {visibleMetrics.length > 0 ? (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
            Metrics
          </p>
          <div className="space-y-2">{visibleMetrics.map((metric) => renderFieldRow(metric))}</div>
        </div>
      ) : null}

      {filteredTables.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
          No fields match this search.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTables.map((table) => (
            <details
              key={table.tableKey}
              className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-3"
            >
              <summary className="cursor-pointer text-sm font-semibold text-[color:var(--text-primary)]">
                {table.tableKey} ({table.schema}.{table.name})
              </summary>
              {table.description ? (
                <p className="mt-2 text-xs text-[color:var(--text-muted)]">{table.description}</p>
              ) : null}
              <div className="mt-3 space-y-3">
                <div className="space-y-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
                    Dimensions
                  </p>
                  {table.dimensions.length === 0 ? (
                    <p className="text-xs text-[color:var(--text-muted)]">None</p>
                  ) : (
                    <div className="space-y-2">
                      {table.dimensions.map((field) => renderFieldRow(field))}
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
                    Measures
                  </p>
                  {table.measures.length === 0 ? (
                    <p className="text-xs text-[color:var(--text-muted)]">None</p>
                  ) : (
                    <div className="space-y-2">
                      {table.measures.map((field) => renderFieldRow(field))}
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
                    Segments
                  </p>
                  {table.segments.length === 0 ? (
                    <p className="text-xs text-[color:var(--text-muted)]">None</p>
                  ) : (
                    <div className="space-y-2">
                      {table.segments.map((field) => renderFieldRow(field))}
                    </div>
                  )}
                </div>
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

function SelectedFieldGroup({
  title,
  selected,
  kind,
  activeFieldId,
  fieldLookup,
  aliases,
  draggingField,
  onActivate,
  onRemove,
  onDragStart,
  onDragEnd,
  onDrop,
}: {
  title: string;
  selected: string[];
  kind: 'dimension' | 'measure';
  activeFieldId: string | null;
  fieldLookup: Map<string, FieldOption>;
  aliases: Record<string, string>;
  draggingField: { id: string; kind: 'dimension' | 'measure' } | null;
  onActivate: (id: string) => void;
  onRemove: (id: string) => void;
  onDragStart: (id: string) => void;
  onDragEnd: () => void;
  onDrop: (targetId: string) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-semibold text-[color:var(--text-primary)]">{title}</p>
      {selected.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
          No {title.toLowerCase()} selected.
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {selected.map((fieldId) => {
            const field = fieldLookup.get(fieldId);
            if (!field) {
              return null;
            }
            const active = activeFieldId === fieldId;
            const isDragging = draggingField?.id === fieldId;
            const displayLabel = aliases[fieldId]?.trim() || field.label;
            return (
              <div
                key={fieldId}
                role="button"
                tabIndex={0}
                onClick={() => onActivate(fieldId)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onActivate(fieldId);
                  }
                }}
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.effectAllowed = 'move';
                  onDragStart(fieldId);
                }}
                onDragEnd={onDragEnd}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  onDrop(fieldId);
                }}
                className={cn(
                  'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition',
                  active
                    ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]'
                    : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-secondary)]',
                  isDragging ? 'opacity-60' : '',
                )}
                title={field.description ?? field.label}
              >
                <span className="text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
                  {field.kind === 'metric' ? 'metric' : kind}
                </span>
                <span>{displayLabel}</span>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onRemove(fieldId);
                  }}
                  className="rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-2 py-0.5 text-[11px] text-[color:var(--text-muted)] transition hover:text-[color:var(--text-primary)]"
                >
                  x
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ResultsTable({
  rows,
  hasRunQuery,
  isLoading,
}: {
  rows: Array<Record<string, unknown>>;
  hasRunQuery: boolean;
  isLoading: boolean;
}) {
  if (isLoading && rows.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
        Running query...
      </div>
    );
  }

  if (!hasRunQuery) {
    return (
      <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
        Run a query to view results.
      </div>
    );
  }

  if (!rows || rows.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-sm">
        No results returned. Adjust fields or filters.
      </div>
    );
  }

  const columns = Object.keys(rows[0]);
  const previewRows = rows.slice(0, 50);

  return (
    <div className="overflow-x-auto rounded-2xl border border-[color:var(--panel-border)]">
      {isLoading ? (
        <div className="border-b border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-2 text-xs text-[color:var(--text-muted)]">
          Refreshing results...
        </div>
      ) : null}
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
  const metricOptions: FieldOption[] = [];

  if (!semanticModel) {
    return { dimensionOptions, measureOptions, segmentOptions, metricOptions };
  }

  Object.entries(semanticModel.tables ?? {}).forEach(([tableKey, table]) => {
    (table.dimensions ?? []).forEach((dimension) => {
      dimensionOptions.push({
        id: `${tableKey}.${dimension.name}`,
        label: `${tableKey} / ${dimension.name}`,
        tableKey,
        type: dimension.type,
        description: dimension.description ?? null,
        kind: 'dimension',
      });
    });
    (table.measures ?? []).forEach((measure) => {
      measureOptions.push({
        id: `${tableKey}.${measure.name}`,
        label: `${tableKey} / ${measure.name}`,
        tableKey,
        type: measure.type,
        description: measure.description ?? null,
        aggregation: measure.aggregation ?? null,
        kind: 'measure',
      });
    });
    Object.entries(table.filters ?? {}).forEach(([filterKey, filter]) => {
      segmentOptions.push({
        id: `${tableKey}.${filterKey}`,
        label: `${tableKey} / ${filterKey}`,
        tableKey,
        description: filter.description ?? null,
        kind: 'segment',
      });
    });
  });

  Object.entries(semanticModel.metrics ?? {}).forEach(([metricName, metric]) => {
    metricOptions.push({
      id: metricName,
      label: `metric / ${metricName}`,
      description: metric.description ?? null,
      kind: 'metric',
    });
  });

  return {
    dimensionOptions,
    measureOptions: [...measureOptions, ...metricOptions],
    segmentOptions,
    metricOptions,
  };
}

function buildTableGroups(semanticModel?: SemanticModelPayload): TableGroup[] {
  if (!semanticModel) {
    return [];
  }

  return Object.entries(semanticModel.tables ?? {}).map(([tableKey, table]) => {
    const dimensions: FieldOption[] = (table.dimensions ?? []).map((dimension) => ({
      id: `${tableKey}.${dimension.name}`,
      label: `${tableKey} / ${dimension.name}`,
      tableKey,
      type: dimension.type,
      description: dimension.description ?? null,
      kind: 'dimension',
    }));
    const measures: FieldOption[] = (table.measures ?? []).map((measure) => ({
      id: `${tableKey}.${measure.name}`,
      label: `${tableKey} / ${measure.name}`,
      tableKey,
      type: measure.type,
      description: measure.description ?? null,
      aggregation: measure.aggregation ?? null,
      kind: 'measure',
    }));
    const segments: FieldOption[] = Object.entries(table.filters ?? {}).map(
      ([filterKey, filter]) => ({
        id: `${tableKey}.${filterKey}`,
        label: `${tableKey} / ${filterKey}`,
        tableKey,
        description: filter.description ?? null,
        kind: 'segment',
      }),
    );

    return {
      tableKey,
      schema: table.schema,
      name: table.name,
      description: table.description ?? null,
      dimensions,
      measures,
      segments,
    };
  });
}

function getFieldKindLabel(kind: FieldOption['kind']): string {
  switch (kind) {
    case 'dimension':
      return 'Dim';
    case 'measure':
      return 'Meas';
    case 'metric':
      return 'Metric';
    case 'segment':
      return 'Seg';
    default:
      return 'Field';
  }
}

function getFilterInputType(type?: string): 'text' | 'number' | 'date' {
  if (!type) {
    return 'text';
  }
  const normalized = type.toLowerCase();
  if (normalized.includes('date') || normalized.includes('time')) {
    return 'date';
  }
  if (
    normalized.includes('int') ||
    normalized.includes('float') ||
    normalized.includes('double') ||
    normalized.includes('decimal') ||
    normalized.includes('number')
  ) {
    return 'number';
  }
  return 'text';
}

function isTimeDimensionOption(option: FieldOption): boolean {
  const normalized = option.type?.toLowerCase() ?? '';
  if (normalized.includes('date') || normalized.includes('time') || normalized.includes('timestamp')) {
    return true;
  }
  if (!normalized) {
    const label = option.label.toLowerCase();
    return /(^|\\W|_)date($|\\W|_)/.test(label) || /(^|\\W|_)time($|\\W|_)/.test(label);
  }
  return false;
}

function aliasForMember(value: string): string {
  return value.replace(/\./g, '__').replace(/ /g, '_').replace(/[^A-Za-z0-9_]+/g, '_');
}

function buildTimeDimensionAlias(member: string, granularity: string): string {
  if (!member) {
    return '';
  }
  const base = aliasForMember(member);
  return granularity ? `${base}_${granularity}` : base;
}

function reorderList(list: string[], fromId: string, toId: string): string[] {
  if (fromId === toId) {
    return list;
  }
  const fromIndex = list.indexOf(fromId);
  const toIndex = list.indexOf(toId);
  if (fromIndex < 0 || toIndex < 0) {
    return list;
  }
  const next = [...list];
  next.splice(fromIndex, 1);
  next.splice(toIndex, 0, fromId);
  return next;
}

function moveItem(list: string[], id: string, offset: number): string[] {
  const index = list.indexOf(id);
  if (index < 0) {
    return list;
  }
  const nextIndex = Math.max(0, Math.min(list.length - 1, index + offset));
  if (index === nextIndex) {
    return list;
  }
  const next = [...list];
  next.splice(index, 1);
  next.splice(nextIndex, 0, id);
  return next;
}

function addSelection(
  value: string,
  selected: string[],
  setSelected: (values: string[]) => void,
) {
  if (selected.includes(value)) {
    return;
  }
  setSelected([...selected, value]);
}

function buildSqlPreview({
  semanticModelName,
  selectedDimensions,
  selectedMeasures,
  selectedSegments,
  selectedTimeDimension,
  timeGrain,
  timeRangePreset,
  timeRangeStart,
  timeRangeEnd,
  orderBys,
  filters,
  limit,
  filterLogic,
}: {
  semanticModelName: string | null;
  selectedDimensions: string[];
  selectedMeasures: string[];
  selectedSegments: string[];
  selectedTimeDimension: string;
  timeGrain: string;
  timeRangePreset: string;
  timeRangeStart: string;
  timeRangeEnd: string;
  orderBys: OrderByDraft[];
  filters: FilterDraft[];
  limit: number;
  filterLogic: 'and' | 'or';
}): string {
  const selectFields = [...selectedDimensions, ...selectedMeasures];
  if (selectedTimeDimension) {
    const timeExpression = timeGrain
      ? `date_trunc('${timeGrain}', ${selectedTimeDimension})`
      : selectedTimeDimension;
    selectFields.push(timeExpression);
  }
  const selectClause = selectFields.length > 0 ? selectFields.join(', ') : '*';
  let sql = `select ${selectClause}\nfrom ${semanticModelName ?? 'semantic_model'}`;

  const filterClauses = filters
    .filter((filter) => filter.member && filter.operator)
    .map((filter) => {
      const values = parseFilterValues(filter);
      if (!values || values.length === 0) {
        return `${filter.member} ${filter.operator}`;
      }
      const formattedValues = values
        .map((value) => `'${value.replace(/'/g, "''")}'`)
        .join(', ');
      return `${filter.member} ${filter.operator} (${formattedValues})`;
    });

  if (filterClauses.length > 0) {
    sql += `\nwhere ${filterClauses.join(filterLogic === 'or' ? ' or ' : ' and ')}`;
  }
  const timeRange = buildTimeRange({
    preset: timeRangePreset,
    start: timeRangeStart,
    end: timeRangeEnd,
  });
  if (selectedTimeDimension && timeRange) {
    sql += `\n-- time range: ${Array.isArray(timeRange) ? timeRange.join(' to ') : timeRange}`;
  }
  if (selectedSegments.length > 0) {
    sql += `\n-- segments: ${selectedSegments.join(', ')}`;
  }
  const orderItems = orderBys
    .filter((item) => item.member)
    .map((item) => `${item.member} ${item.direction}`);
  if (orderItems.length > 0) {
    sql += `\norder by ${orderItems.join(', ')}`;
  }
  if (limit) {
    sql += `\nlimit ${limit}`;
  }

  return sql;
}

function toCsvValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  const baseValue =
    typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
      ? String(value)
      : JSON.stringify(value);
  const escaped = baseValue.replace(/"/g, '""');
  if (/[",\n]/.test(escaped)) {
    return `"${escaped}"`;
  }
  return escaped;
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
  if (filter.operator === 'set' || filter.operator === 'notset') {
    return undefined;
  }
  if (!filter.values) {
    return undefined;
  }
  const values = filter.values
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
  return values.length > 0 ? values : undefined;
}

function buildTimeRange({
  preset,
  start,
  end,
}: {
  preset: string;
  start: string;
  end: string;
}): string | string[] | undefined {
  if (preset) {
    return preset;
  }
  if (start && end) {
    return [start, end];
  }
  if (start) {
    return start;
  }
  if (end) {
    return end;
  }
  return undefined;
}

function buildOrderPayload(
  orderBys: OrderByDraft[],
): Record<string, 'asc' | 'desc'> | Array<Record<string, 'asc' | 'desc'>> | undefined {
  const items = orderBys.filter((item) => item.member);
  if (items.length === 0) {
    return undefined;
  }
  if (items.length === 1) {
    return { [items[0].member]: items[0].direction };
  }
  return items.map((item) => ({ [item.member]: item.direction }));
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
