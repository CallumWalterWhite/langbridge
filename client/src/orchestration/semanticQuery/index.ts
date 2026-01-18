import { apiFetch } from '@/orchestration/http';

import type {
  SemanticQueryMetaResponse,
  SemanticQueryRequestPayload,
  SemanticQueryResponse,
} from './types';

const BASE_PATH = '/api/v1/semantic-query';

export async function fetchSemanticQueryMeta(
  semanticModelId: string,
  organizationId: string,
): Promise<SemanticQueryMetaResponse> {
  const params = new URLSearchParams({ organization_id: organizationId });
  return apiFetch<SemanticQueryMetaResponse>(`${BASE_PATH}/${semanticModelId}/meta?${params.toString()}`);
}

export async function runSemanticQuery(
  payload: SemanticQueryRequestPayload,
): Promise<SemanticQueryResponse> {
  return apiFetch<SemanticQueryResponse>(`${BASE_PATH}/${payload.semanticModelId}/q`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
