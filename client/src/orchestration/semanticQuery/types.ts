export interface SemanticDimensionPayload {
  name: string;
  type: string;
  primary_key?: boolean;
  alias?: string | null;
  description?: string | null;
  synonyms?: string[] | null;
  vectorized?: boolean;
  vector_reference?: string | null;
  vector_index?: Record<string, unknown> | null;
}

export interface SemanticMeasurePayload {
  name: string;
  type: string;
  description?: string | null;
  aggregation?: string | null;
  synonyms?: string[] | null;
}

export interface SemanticFilterPayload {
  condition: string;
  description?: string | null;
  synonyms?: string[] | null;
}

export interface SemanticTablePayload {
  schema: string;
  name: string;
  description?: string | null;
  synonyms?: string[] | null;
  dimensions?: SemanticDimensionPayload[] | null;
  measures?: SemanticMeasurePayload[] | null;
  filters?: Record<string, SemanticFilterPayload> | null;
}

export interface SemanticRelationshipPayload {
  name: string;
  from_: string;
  to: string;
  type: string;
  join_on: string;
}

export interface SemanticMetricPayload {
  description?: string | null;
  expression: string;
}

export interface SemanticModelPayload {
  version: string;
  name?: string | null;
  connector?: string | null;
  dialect?: string | null;
  description?: string | null;
  tags?: string[] | null;
  tables: Record<string, SemanticTablePayload>;
  relationships?: SemanticRelationshipPayload[] | null;
  metrics?: Record<string, SemanticMetricPayload> | null;
}

export interface SemanticQueryMetaResponse {
  id: string;
  name: string;
  description?: string | null;
  connectorId: string;
  organizationId: string;
  projectId?: string | null;
  semanticModel: SemanticModelPayload;
}

export interface SemanticQueryFilter {
  member?: string;
  dimension?: string;
  measure?: string;
  timeDimension?: string;
  operator: string;
  values?: string[];
}

export interface SemanticQueryTimeDimension {
  dimension: string;
  granularity?: string;
  dateRange?: string | string[];
  compareDateRange?: string | string[];
}

export interface SemanticQueryPayload {
  measures?: string[];
  dimensions?: string[];
  timeDimensions?: SemanticQueryTimeDimension[];
  filters?: SemanticQueryFilter[];
  segments?: string[];
  order?: Record<string, 'asc' | 'desc'>;
  limit?: number;
  offset?: number;
  timezone?: string;
}

export interface SemanticQueryRequestPayload {
  organizationId: string;
  projectId?: string | null;
  semanticModelId: string;
  query: SemanticQueryPayload;
}

export interface SemanticQueryResponse {
  id: string;
  organizationId: string;
  projectId?: string | null;
  semanticModelId: string;
  data: Array<Record<string, unknown>>;
  annotations: Array<Record<string, unknown>>;
}
