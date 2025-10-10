import { apiFetch } from '@/orchestration/http';

import type {
  CreateSemanticModelPayload,
  SemanticModel,
  SemanticModelRecord,
} from './types';

const BASE_PATH = '/api/v1/semantic-model';

export async function previewSemanticModel(
  organizationId: string,
  projectId?: string,
): Promise<SemanticModel> {
  const params = new URLSearchParams({ organization_id: organizationId });
  if (projectId) {
    params.set('project_id', projectId);
  }
  return apiFetch<SemanticModel>(`${BASE_PATH}/preview?${params.toString()}`);
}

export async function listSemanticModels(
  organizationId: string,
  projectId?: string,
): Promise<SemanticModelRecord[]> {
  const params = new URLSearchParams({ organization_id: organizationId });
  if (projectId) {
    params.set('project_id', projectId);
  }
  return apiFetch<SemanticModelRecord[]>(`${BASE_PATH}?${params.toString()}`);
}

export async function createSemanticModel(payload: CreateSemanticModelPayload): Promise<SemanticModelRecord> {
  return apiFetch<SemanticModelRecord>(BASE_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteSemanticModel(
  modelId: string,
  organizationId: string,
): Promise<void> {
  const params = new URLSearchParams({ organization_id: organizationId });
  await apiFetch<void>(`${BASE_PATH}/${modelId}?${params.toString()}`, {
    method: 'DELETE',
    skipJsonParse: true,
  });
}

export async function fetchSemanticModel(
  modelId: string,
  organizationId: string,
): Promise<SemanticModelRecord> {
  const params = new URLSearchParams({ organization_id: organizationId });
  return apiFetch<SemanticModelRecord>(`${BASE_PATH}/${modelId}?${params.toString()}`);
}

export async function previewSemanticModelYaml(
  organizationId: string,
  projectId?: string,
): Promise<string> {
  const params = new URLSearchParams({ organization_id: organizationId });
  if (projectId) {
    params.set('project_id', projectId);
  }
  const response = await fetch(`${BASE_PATH}/preview/yaml?${params.toString()}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}

export async function fetchSemanticModelYaml(
  modelId: string,
  organizationId: string,
): Promise<string> {
  const params = new URLSearchParams({ organization_id: organizationId });
  const response = await fetch(`${BASE_PATH}/${modelId}/yaml?${params.toString()}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}
