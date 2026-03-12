export interface SemanticDimension {
  name: string;
  expression?: string | null;
  type: string;
  primaryKey?: boolean;
  alias?: string | null;
  description?: string | null;
  synonyms?: string[] | null;
  vectorized?: boolean;
}

export interface SemanticMeasure {
  name: string;
  expression?: string | null;
  type: string;
  description?: string | null;
  aggregation?: string | null;
  synonyms?: string[] | null;
}

export interface SemanticFilter {
  condition: string;
  description?: string | null;
  synonyms?: string[] | null;
}

export interface SemanticDataset {
  datasetId?: string | null;
  relationName?: string | null;
  schemaName?: string | null;
  catalogName?: string | null;
  description?: string | null;
  synonyms?: string[] | null;
  dimensions?: SemanticDimension[] | null;
  measures?: SemanticMeasure[] | null;
  filters?: Record<string, SemanticFilter> | null;
}

export interface SemanticRelationship {
  name: string;
  sourceDataset: string;
  sourceField: string;
  targetDataset: string;
  targetField: string;
  type: string;
}

export interface SemanticMetric {
  description?: string | null;
  expression: string;
}

export interface SemanticModel {
  version: string;
  connector?: string | null;
  description?: string | null;
  datasets: Record<string, SemanticDataset>;
  relationships?: SemanticRelationship[] | null;
  metrics?: Record<string, SemanticMetric> | null;
  tables?: Record<string, SemanticDataset>;
}

export interface SemanticModelRecord {
  id: string;
  organizationId: string;
  projectId?: string | null;
  connectorId?: string | null;
  name: string;
  description?: string | null;
  contentYaml: string;
  createdAt: string;
  updatedAt: string;
  sourceDatasetIds?: string[];
}

export interface CreateSemanticModelPayload {
  organizationId: string;
  projectId?: string | null;
  connectorId?: string | null;
  name: string;
  description?: string;
  autoGenerate?: boolean;
  modelYaml?: string;
  sourceDatasetIds?: string[];
}

export interface UpdateSemanticModelPayload {
  projectId?: string | null;
  connectorId?: string | null;
  name?: string;
  description?: string;
  autoGenerate?: boolean;
  modelYaml?: string;
  sourceDatasetIds?: string[];
}

export interface SemanticModelCatalogField {
  name: string;
  type: string;
  nullable?: boolean | null;
  primaryKey?: boolean;
}

export interface SemanticModelCatalogDataset {
  id: string;
  name: string;
  sqlAlias: string;
  description?: string | null;
  connectionId?: string | null;
  sourceKind: string;
  storageKind: string;
  fields: SemanticModelCatalogField[];
}

export interface SemanticModelCatalogResponse {
  workspaceId: string;
  items: SemanticModelCatalogDataset[];
}

export interface SemanticModelSelectionGeneratePayload {
  datasetIds: string[];
  selectedFields?: Record<string, string[]>;
  includeSampleValues?: boolean;
  description?: string;
}

export interface SemanticModelSelectionGenerateResponse {
  yamlText: string;
  warnings: string[];
}

export interface SemanticModelAgenticJobCreatePayload {
  projectId?: string | null;
  name: string;
  description?: string;
  filename?: string;
  datasetIds: string[];
  questionPrompts: string[];
  includeSampleValues?: boolean;
}

export interface SemanticModelAgenticJobCreateResponse {
  jobId: string;
  jobStatus: string;
  semanticModelId: string;
}

export type SemanticModelKind = 'all' | 'standard' | 'unified';
