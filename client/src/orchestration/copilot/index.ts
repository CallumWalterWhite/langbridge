import { apiFetch } from '@/orchestration/http';
import type {
  QueryBuilderCopilotRequestPayload,
  QueryBuilderCopilotResponsePayload,
} from './types';

const BASE_PATH = '/api/v1/copilot';

function requireOrganizationId(organizationId: string): string {
  if (!organizationId) {
    throw new Error('Organization id is required.');
  }
  return organizationId;
}

function basePath(organizationId: string): string {
  return `${BASE_PATH}/${requireOrganizationId(organizationId)}`;
}

export async function runCopilot(
  organizationId: string,
  agentId: string,
  payload: QueryBuilderCopilotRequestPayload,
): Promise<QueryBuilderCopilotResponsePayload> {
  if (!agentId) {
    throw new Error('Copilot agent id is required.');
  }
  return apiFetch<QueryBuilderCopilotResponsePayload>(`${basePath(organizationId)}/${agentId}/assist`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
