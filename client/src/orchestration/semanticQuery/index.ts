import { apiFetch } from '@/orchestration/http';

import type {
  SemanticQueryJobResponse,
  SemanticQueryMetaResponse,
  SemanticQueryRequestPayload,
  SemanticQueryResponse,
  UnifiedSemanticQueryMetaRequestPayload,
  UnifiedSemanticQueryMetaResponse,
  UnifiedSemanticQueryRequestPayload,
  UnifiedSemanticQueryResponse,
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

export async function fetchUnifiedSemanticQueryMeta(
  organizationId: string,
  payload: UnifiedSemanticQueryMetaRequestPayload,
): Promise<UnifiedSemanticQueryMetaResponse> {
  return apiFetch<UnifiedSemanticQueryMetaResponse>(`${basePath(organizationId)}/unified/meta`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function runUnifiedSemanticQuery(
  organizationId: string,
  payload: UnifiedSemanticQueryRequestPayload,
): Promise<UnifiedSemanticQueryResponse> {
  return apiFetch<UnifiedSemanticQueryResponse>(`${basePath(organizationId)}/unified/q`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function enqueueUnifiedSemanticQuery(
  organizationId: string,
  payload: UnifiedSemanticQueryRequestPayload,
): Promise<SemanticQueryJobResponse> {
  return apiFetch<SemanticQueryJobResponse>(`${basePath(organizationId)}/unified/q/jobs`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
