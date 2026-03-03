import { apiFetch } from '@/orchestration/http';

import type {
  DatasetCatalogResponse,
  DatasetCreatePayload,
  DatasetListResponse,
  DatasetPreviewRequestPayload,
  DatasetPreviewResponse,
  DatasetProfileRequestPayload,
  DatasetProfileResponse,
  DatasetRecord,
  DatasetUpdatePayload,
  DatasetUsageResponse,
} from './types';

const DATASET_BASE_PATH = '/api/v1/datasets';

function requiredWorkspaceId(workspaceId: string): string {
  if (!workspaceId) {
    throw new Error('Workspace id is required.');
  }
  return workspaceId;
}

export async function listDatasets(
  workspaceId: string,
  options?: {
    projectId?: string | null;
    search?: string;
    tags?: string[];
    datasetTypes?: string[];
  },
): Promise<DatasetListResponse> {
  const params = new URLSearchParams({ workspace_id: requiredWorkspaceId(workspaceId) });
  if (options?.projectId) {
    params.set('project_id', options.projectId);
  }
  if (options?.search) {
    params.set('search', options.search);
  }
  for (const tag of options?.tags || []) {
    if (tag.trim()) {
      params.append('tags', tag.trim());
    }
  }
  for (const item of options?.datasetTypes || []) {
    if (item.trim()) {
      params.append('dataset_types', item.trim());
    }
  }
  return apiFetch<DatasetListResponse>(`${DATASET_BASE_PATH}?${params.toString()}`);
}

export async function createDataset(payload: DatasetCreatePayload): Promise<DatasetRecord> {
  return apiFetch<DatasetRecord>(DATASET_BASE_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getDataset(datasetId: string, workspaceId: string): Promise<DatasetRecord> {
  if (!datasetId) {
    throw new Error('Dataset id is required.');
  }
  const params = new URLSearchParams({ workspace_id: requiredWorkspaceId(workspaceId) });
  return apiFetch<DatasetRecord>(`${DATASET_BASE_PATH}/${encodeURIComponent(datasetId)}?${params.toString()}`);
}

export async function updateDataset(datasetId: string, payload: DatasetUpdatePayload): Promise<DatasetRecord> {
  if (!datasetId) {
    throw new Error('Dataset id is required.');
  }
  return apiFetch<DatasetRecord>(`${DATASET_BASE_PATH}/${encodeURIComponent(datasetId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteDataset(datasetId: string, workspaceId: string): Promise<void> {
  if (!datasetId) {
    throw new Error('Dataset id is required.');
  }
  const params = new URLSearchParams({ workspace_id: requiredWorkspaceId(workspaceId) });
  await apiFetch<void>(`${DATASET_BASE_PATH}/${encodeURIComponent(datasetId)}?${params.toString()}`, {
    method: 'DELETE',
    skipJsonParse: true,
  });
}

export async function previewDataset(
  datasetId: string,
  payload: DatasetPreviewRequestPayload,
): Promise<DatasetPreviewResponse> {
  if (!datasetId) {
    throw new Error('Dataset id is required.');
  }
  return apiFetch<DatasetPreviewResponse>(`${DATASET_BASE_PATH}/${encodeURIComponent(datasetId)}/preview`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function profileDataset(
  datasetId: string,
  payload: DatasetProfileRequestPayload,
): Promise<DatasetProfileResponse> {
  if (!datasetId) {
    throw new Error('Dataset id is required.');
  }
  return apiFetch<DatasetProfileResponse>(`${DATASET_BASE_PATH}/${encodeURIComponent(datasetId)}/profile`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchDatasetCatalog(
  workspaceId: string,
  projectId?: string | null,
): Promise<DatasetCatalogResponse> {
  const params = new URLSearchParams({ workspace_id: requiredWorkspaceId(workspaceId) });
  if (projectId) {
    params.set('project_id', projectId);
  }
  return apiFetch<DatasetCatalogResponse>(`${DATASET_BASE_PATH}/catalog?${params.toString()}`);
}

export async function fetchDatasetUsage(
  datasetId: string,
  workspaceId: string,
): Promise<DatasetUsageResponse> {
  if (!datasetId) {
    throw new Error('Dataset id is required.');
  }
  const params = new URLSearchParams({ workspace_id: requiredWorkspaceId(workspaceId) });
  return apiFetch<DatasetUsageResponse>(`${DATASET_BASE_PATH}/${encodeURIComponent(datasetId)}/used-by?${params.toString()}`);
}

export type {
  DatasetCatalogItem,
  DatasetCatalogResponse,
  DatasetColumn,
  DatasetCreatePayload,
  DatasetListResponse,
  DatasetPolicy,
  DatasetPreviewRequestPayload,
  DatasetPreviewResponse,
  DatasetProfileRequestPayload,
  DatasetProfileResponse,
  DatasetRecord,
  DatasetStatus,
  DatasetType,
  DatasetUpdatePayload,
  DatasetUsageResponse,
} from './types';
