import { apiFetch } from '@/orchestration/http';

import type {
  SemanticQueryJobResponse,
  SemanticQueryMetaResponse,
  SemanticQueryRequestPayload,
  SemanticQueryResponse,
} from './types';

const BASE_PATH = '/api/v1/semantic-query';

function requireOrganizationId(organizationId: string): string {
  if (!organizationId) {
    throw new Error('Organization id is required.');
  }
  return organizationId;
}

function basePath(organizationId: string): string {
  return `${BASE_PATH}/${requireOrganizationId(organizationId)}`;
}

export async function fetchSemanticQueryMeta(
  organizationId: string,
  semanticModelId: string,
): Promise<SemanticQueryMetaResponse> {
  return apiFetch<SemanticQueryMetaResponse>(
    `${basePath(organizationId)}/${semanticModelId}/meta`,
  );
}

export async function runSemanticQuery(
  organizationId: string,
  payload: SemanticQueryRequestPayload,
): Promise<SemanticQueryResponse> {
  return apiFetch<SemanticQueryResponse>(`${basePath(organizationId)}/${payload.semanticModelId}/q`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function enqueueSemanticQuery(
  organizationId: string,
  payload: SemanticQueryRequestPayload,
): Promise<SemanticQueryJobResponse> {
  return apiFetch<SemanticQueryJobResponse>(
    `${basePath(organizationId)}/${payload.semanticModelId}/q/jobs`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}
