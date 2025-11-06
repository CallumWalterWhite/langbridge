import { apiFetch } from '../http';
import type {
  CreateLLMConnectionPayload,
  LLMConnection,
  LLMConnectionApiResponse,
  LLMConnectionTestResult,
  TestLLMConnectionPayload,
  UpdateLLMConnectionPayload,
} from './types';

const BASE_PATH = '/api/v1/agents/llm-connections';

function normalizeConnection(payload: LLMConnectionApiResponse): LLMConnection {
  return {
    id: payload.id,
    name: payload.name,
    provider: payload.provider,
    model: payload.model,
    description: payload.description ?? null,
    configuration: payload.configuration ?? null,
    isActive: payload.is_active,
    organizationId: payload.organization_id ?? null,
    projectId: payload.project_id ?? null,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  };
}

export async function fetchLLMConnections(): Promise<LLMConnection[]> {
  const response = await apiFetch<LLMConnectionApiResponse[]>(BASE_PATH);
  return response.map(normalizeConnection);
}

export async function fetchLLMConnection(connectionId: string): Promise<LLMConnection> {
  const response = await apiFetch<LLMConnectionApiResponse>(`${BASE_PATH}/${connectionId}`);
  return normalizeConnection(response);
}

export async function createLLMConnection(payload: CreateLLMConnectionPayload): Promise<LLMConnection> {
  const body: Record<string, unknown> = {
    name: payload.name,
    provider: payload.provider,
    model: payload.model,
    api_key: payload.apiKey,
    description: payload.description,
    configuration: payload.configuration ?? {},
  };

  if (payload.organizationId) {
    body.organization_id = payload.organizationId;
  }

  if (payload.projectId) {
    body.project_id = payload.projectId;
  }

  const response = await apiFetch<LLMConnectionApiResponse>(BASE_PATH, {
    method: 'POST',
    body: JSON.stringify(body),
  });

  return normalizeConnection(response);
}

export async function updateLLMConnection(
  connectionId: string,
  payload: UpdateLLMConnectionPayload,
): Promise<LLMConnection> {
  const body: Record<string, unknown> = {
    name: payload.name,
    api_key: payload.apiKey,
    model: payload.model,
    configuration: payload.configuration ?? {},
    is_active: payload.isActive,
  };

  if (typeof payload.description === 'string') {
    body.description = payload.description;
  }
  if (payload.organizationId) {
    body.organization_id = payload.organizationId;
  }
  if (payload.projectId) {
    body.project_id = payload.projectId;
  }

  const response = await apiFetch<LLMConnectionApiResponse>(`${BASE_PATH}/${connectionId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });

  return normalizeConnection(response);
}

export async function testLLMConnection(payload: TestLLMConnectionPayload): Promise<LLMConnectionTestResult> {
  return apiFetch<LLMConnectionTestResult>(`${BASE_PATH}/test`, {
    method: 'POST',
    body: JSON.stringify({
      provider: payload.provider,
      api_key: payload.apiKey,
      model: payload.model,
      configuration: payload.configuration ?? {},
    }),
  });
}

export type {
  CreateLLMConnectionPayload,
  LLMConnection,
  LLMConnectionApiResponse,
  LLMConnectionTestResult,
  TestLLMConnectionPayload,
  UpdateLLMConnectionPayload,
} from './types';
