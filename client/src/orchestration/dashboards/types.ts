export interface DashboardRecord {
  id: string;
  organizationId: string;
  projectId?: string | null;
  semanticModelId: string;
  name: string;
  description?: string | null;
  refreshMode: 'manual' | 'live';
  dataSnapshotFormat: 'json';
  lastRefreshedAt?: string | null;
  globalFilters: Array<Record<string, unknown>>;
  widgets: Array<Record<string, unknown>>;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface DashboardCreatePayload {
  projectId?: string | null;
  semanticModelId: string;
  name: string;
  description?: string | null;
  refreshMode: 'manual' | 'live';
  globalFilters: Array<Record<string, unknown>>;
  widgets: Array<Record<string, unknown>>;
}

export interface DashboardUpdatePayload {
  projectId?: string | null;
  semanticModelId?: string;
  name?: string;
  description?: string | null;
  refreshMode?: 'manual' | 'live';
  globalFilters?: Array<Record<string, unknown>>;
  widgets?: Array<Record<string, unknown>>;
}

export interface DashboardSnapshotRecord {
  dashboardId: string;
  snapshotFormat: 'json';
  capturedAt: string;
  data: Record<string, unknown>;
}

export interface DashboardSnapshotUpsertPayload {
  data: Record<string, unknown>;
  capturedAt?: string | null;
}
