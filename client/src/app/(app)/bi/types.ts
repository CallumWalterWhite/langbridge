import type { SemanticQueryResponse } from '@/orchestration/semanticQuery/types';

export type FieldOption = {
  id: string;
  label: string;
  tableKey?: string;
  type?: string;
  description?: string | null;
  aggregation?: string | null;
  kind: 'dimension' | 'measure' | 'metric' | 'segment';
};

export type TableGroup = {
  tableKey: string;
  schema: string;
  name: string;
  description?: string | null;
  dimensions: FieldOption[];
  measures: FieldOption[];
  segments: FieldOption[];
};

export type ChartType = 'table' | 'bar' | 'line' | 'pie';
export type WidgetSize = 'small' | 'wide' | 'tall' | 'large';

export type FilterDraft = {
  id: string;
  member: string;
  operator: string;
  values: string;
};

export type OrderByDraft = {
  id: string;
  member: string;
  direction: 'asc' | 'desc';
};

export type BiWidget = {
  id: string;
  title: string;
  type: ChartType;
  size: WidgetSize;
  // Data State
  measures: string[];
  dimensions: string[];
  filters: FilterDraft[];
  orderBys: OrderByDraft[];
  limit: number;
  timeDimension: string;
  timeGrain: string;
  timeRangePreset: string;
  // Visual State
  chartX: string;
  chartY: string;
  // Execution State
  queryResult: SemanticQueryResponse | null;
  isLoading: boolean;
  jobId?: string | null;
  jobStatus?: string | null;
  progress?: number;
  statusMessage?: string | null;
  error?: string | null;
};

export type PersistedBiWidget = Omit<
  BiWidget,
  'queryResult' | 'isLoading' | 'jobId' | 'jobStatus' | 'progress' | 'statusMessage' | 'error'
>;

export type DashboardBuilderState = {
  name: string;
  description: string;
  refreshMode: 'manual' | 'live';
  semanticModelId: string;
  globalFilters: FilterDraft[];
  widgets: PersistedBiWidget[];
};

export const FILTER_OPERATORS = [
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

export const TIME_GRAIN_OPTIONS = [
  { value: '', label: 'No grain' },
  { value: 'day', label: 'Day' },
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
  { value: 'quarter', label: 'Quarter' },
  { value: 'year', label: 'Year' },
];

export const DATE_PRESETS = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'month_to_date', label: 'Month to date' },
  { value: 'year_to_date', label: 'Year to date' },
];
