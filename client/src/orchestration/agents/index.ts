import { apiFetch } from '../http';
import type {
  AgentDefinition,
  AgentDefinitionApiResponse,
  CreateAgentDefinitionPayload,
  CreateLLMConnectionPayload,
  LLMConnection,
  LLMConnectionApiResponse,
  LLMConnectionTestResult,
  TestLLMConnectionPayload,
  UpdateAgentDefinitionPayload,
  UpdateLLMConnectionPayload,
} from './types';

const BASE_PATH = '/api/v1/agents/llm-connections';
const DEF_BASE_PATH = '/api/v1/agents/definitions';

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

function normalizeDefinition(payload: AgentDefinitionApiResponse): AgentDefinition {
  let parsedDefinition: unknown = payload.definition;
  if (typeof parsedDefinition === 'string') {
    try {
      parsedDefinition = JSON.parse(parsedDefinition);
    } catch {
      parsedDefinition = payload.definition;
    }
  }

  const asAny = payload as any;
  return {
    id: payload.id,
    name: payload.name,
    description: payload.description ?? null,
    llmConnectionId: asAny.llm_connection_id ?? asAny.llmConnectionId ?? '',
    definition: parsedDefinition,
    isActive: asAny.is_active ?? asAny.isActive ?? true,
    createdAt: asAny.created_at ?? asAny.createdAt ?? '',
    updatedAt: asAny.updated_at ?? asAny.updatedAt ?? '',
  };
}

function serializeDefinition(definition: unknown): string | unknown {
  if (typeof definition === 'string') {
    return definition;
  }
  try {
    return JSON.stringify(definition);
  } catch {
    return definition;
  }
}

export async function fetchAgentDefinitions(): Promise<AgentDefinition[]> {
  const response = await apiFetch<AgentDefinitionApiResponse[]>(DEF_BASE_PATH);
  return response.map(normalizeDefinition);
}

export async function fetchAgentDefinition(agentId: string): Promise<AgentDefinition> {
  const response = await apiFetch<AgentDefinitionApiResponse>(`${DEF_BASE_PATH}/${agentId}`);
  return normalizeDefinition(response);
}

export async function createAgentDefinition(payload: CreateAgentDefinitionPayload): Promise<AgentDefinition> {
  const body: Record<string, unknown> = {
    name: payload.name,
    description: payload.description,
    llm_connection_id: payload.llmConnectionId,
    definition: serializeDefinition(payload.definition),
    is_active: payload.isActive ?? true,
  };

  const response = await apiFetch<AgentDefinitionApiResponse>(DEF_BASE_PATH, {
    method: 'POST',
    body: JSON.stringify(body),
  });

  return normalizeDefinition(response);
}

export async function updateAgentDefinition(
  agentId: string,
  payload: UpdateAgentDefinitionPayload,
): Promise<AgentDefinition> {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.description !== undefined) body.description = payload.description;
  if (payload.llmConnectionId !== undefined) body.llm_connection_id = payload.llmConnectionId;
  if (payload.definition !== undefined) body.definition = serializeDefinition(payload.definition);
  if (payload.isActive !== undefined) body.is_active = payload.isActive;

  const response = await apiFetch<AgentDefinitionApiResponse>(`${DEF_BASE_PATH}/${agentId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });

  return normalizeDefinition(response);
}

export async function deleteAgentDefinition(agentId: string): Promise<void> {
  await apiFetch<void>(`${DEF_BASE_PATH}/${agentId}`, { method: 'DELETE', skipJsonParse: true });
}

export type {
  AgentDefinition,
  AgentDefinitionApiResponse,
  CreateAgentDefinitionPayload,
  CreateLLMConnectionPayload,
  LLMConnection,
  LLMConnectionApiResponse,
  LLMConnectionTestResult,
  TestLLMConnectionPayload,
  UpdateAgentDefinitionPayload,
  UpdateLLMConnectionPayload,
  LLMProvider,
} from './types';
