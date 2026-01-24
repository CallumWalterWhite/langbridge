import { apiFetch } from '../http';
import type {
  AgentDefinition,
  AgentDefinitionApiResponse,
  AgentDefinitionApiResponseLegacy,
  CreateAgentDefinitionPayload,
  CreateLLMConnectionPayload,
  LLMConnection,
  LLMConnectionApiResponse,
  LLMConnectionTestResult,
  TestLLMConnectionPayload,
  UpdateAgentDefinitionPayload,
  UpdateLLMConnectionPayload,
  SemanticModelResponse,
  FileRetriverDefinitionResponse,
  WebSearchDefinitionResponse,
  SemanticSearchDefinitionResponse
} from './types';

const AGENTS_BASE_PATH = '/api/v1/agents';
const SM_BASE_PATH = '/api/v1/semantic-model';

function requireOrganizationId(organizationId: string): string {
  if (!organizationId) {
    throw new Error('Organization ID is required for agent operations.');
  }
  return organizationId;
}

function llmBasePath(organizationId: string): string {
  return `${AGENTS_BASE_PATH}/${requireOrganizationId(organizationId)}/llm-connections`;
}

function definitionsBasePath(organizationId: string): string {
  return `${AGENTS_BASE_PATH}/${requireOrganizationId(organizationId)}/definitions`;
}

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

export async function fetchLLMConnections(organizationId: string): Promise<LLMConnection[]> {
  const response = await apiFetch<LLMConnectionApiResponse[]>(llmBasePath(organizationId));
  return response.map(normalizeConnection);
}

export async function fetchLLMConnection(organizationId: string, connectionId: string): Promise<LLMConnection> {
  const response = await apiFetch<LLMConnectionApiResponse>(`${llmBasePath(organizationId)}/${connectionId}`);
  return normalizeConnection(response);
}

export async function createLLMConnection(
  organizationId: string,
  payload: CreateLLMConnectionPayload,
): Promise<LLMConnection> {
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

  const response = await apiFetch<LLMConnectionApiResponse>(llmBasePath(organizationId), {
    method: 'POST',
    body: JSON.stringify(body),
  });

  return normalizeConnection(response);
}

export async function updateLLMConnection(
  organizationId: string,
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

  const response = await apiFetch<LLMConnectionApiResponse>(
    `${llmBasePath(organizationId)}/${connectionId}`,
    {
      method: 'PUT',
      body: JSON.stringify(body),
    },
  );

  return normalizeConnection(response);
}

export async function testLLMConnection(
  organizationId: string,
  payload: TestLLMConnectionPayload,
): Promise<LLMConnectionTestResult> {
  return apiFetch<LLMConnectionTestResult>(`${llmBasePath(organizationId)}/test`, {
    method: 'POST',
    body: JSON.stringify({
      provider: payload.provider,
      api_key: payload.apiKey,
      model: payload.model,
      configuration: payload.configuration ?? {},
    }),
  });
}

export async function deleteLLMConnection(organizationId: string, connectionId: string): Promise<void> {
  await apiFetch<void>(`${llmBasePath(organizationId)}/${connectionId}`, {
    method: 'DELETE',
    skipJsonParse: true,
  });
}

function normalizeDefinition(payload: AgentDefinitionApiResponse | AgentDefinitionApiResponseLegacy): AgentDefinition {
  let parsedDefinition: unknown = payload.definition;
  if (typeof parsedDefinition === 'string') {
    try {
      parsedDefinition = JSON.parse(parsedDefinition);
    } catch {
      parsedDefinition = payload.definition;
    }
  }

  const legacy = payload as AgentDefinitionApiResponseLegacy;
  return {
    id: payload.id,
    name: payload.name,
    description: payload.description ?? null,
    llmConnectionId: payload.llm_connection_id ?? legacy.llmConnectionId ?? '',
    definition: parsedDefinition,
    isActive: payload.is_active ?? legacy.isActive ?? true,
    createdAt: payload.created_at ?? legacy.createdAt ?? '',
    updatedAt: payload.updated_at ?? legacy.updatedAt ?? '',
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

export async function fetchAgentDefinitions(organizationId: string): Promise<AgentDefinition[]> {
  const response = await apiFetch<AgentDefinitionApiResponse[]>(definitionsBasePath(organizationId));
  return response.map(normalizeDefinition);
}

export async function fetchAgentDefinition(organizationId: string, agentId: string): Promise<AgentDefinition> {
  const response = await apiFetch<AgentDefinitionApiResponse>(
    `${definitionsBasePath(organizationId)}/${agentId}`,
  );
  return normalizeDefinition(response);
}

export async function createAgentDefinition(
  organizationId: string,
  payload: CreateAgentDefinitionPayload,
): Promise<AgentDefinition> {
  const body: Record<string, unknown> = {
    name: payload.name,
    description: payload.description,
    llm_connection_id: payload.llmConnectionId,
    definition: serializeDefinition(payload.definition),
    is_active: payload.isActive ?? true,
  };

  const response = await apiFetch<AgentDefinitionApiResponse>(definitionsBasePath(organizationId), {
    method: 'POST',
    body: JSON.stringify(body),
  });

  return normalizeDefinition(response);
}

export async function updateAgentDefinition(
  organizationId: string,
  agentId: string,
  payload: UpdateAgentDefinitionPayload,
): Promise<AgentDefinition> {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.description !== undefined) body.description = payload.description;
  if (payload.llmConnectionId !== undefined) body.llm_connection_id = payload.llmConnectionId;
  if (payload.definition !== undefined) body.definition = serializeDefinition(payload.definition);
  if (payload.isActive !== undefined) body.is_active = payload.isActive;

  const response = await apiFetch<AgentDefinitionApiResponse>(
    `${definitionsBasePath(organizationId)}/${agentId}`,
    {
      method: 'PUT',
      body: JSON.stringify(body),
    },
  );

  return normalizeDefinition(response);
}

export async function deleteAgentDefinition(organizationId: string, agentId: string): Promise<void> {
  await apiFetch<void>(`${definitionsBasePath(organizationId)}/${agentId}`, {
    method: 'DELETE',
    skipJsonParse: true,
  });
}

export async function getAvailableSemanticModels(
  organizationId: string,
  projectId?: string,
): Promise<SemanticModelResponse[]> {
  const params = new URLSearchParams();
  if (projectId) {
    params.set('project_id', projectId);
  }
  const suffix = params.toString();
  return apiFetch<SemanticModelResponse[]>(
    `${SM_BASE_PATH}/${requireOrganizationId(organizationId)}${suffix ? `?${suffix}` : ''}`,
  );
  // Stub response until backend is implemented
  return Promise.resolve([
    { id: 'semantic-model-1', name: 'Semantic Model 1', description: 'A powerful semantic model for understanding text.' },
    { id: 'semantic-model-2', name: 'Semantic Model 2', description: 'An advanced model for semantic analysis.' },
    { id: 'semantic-model-3', name: 'Semantic Model 3', description: 'A cutting-edge model for deep semantic comprehension.' },
  ]);
}

export async function getAvailableFileRetriverDefinitions(): Promise<FileRetriverDefinitionResponse[]> {
  // return apiFetch<FileRetriverDefinitionResponse[]>(`${DEF_BASE_PATH}/file-retrievers`);
  // Stub response until backend is implemented
  return Promise.resolve([
    { id: 'file-retriever-1', name: 'File Retriever 1', description: 'Retrieves files from various sources efficiently.', },
    { id: 'file-retriever-2', name: 'File Retriever 2', description: 'Advanced file retrieval system for large datasets.', },
  ]);
}

export async function getAvailableWebSearchDefinitions(): Promise<WebSearchDefinitionResponse[]> {
  // return apiFetch<WebSearchDefinitionResponse[]>(`${DEF_BASE_PATH}/web-searches`);
  // Stub response until backend is implemented
  return Promise.resolve([
    { id: 'web-search-1', name: 'Web Search 1', description: 'Performs web searches to gather relevant information.', },
    { id: 'web-search-2', name: 'Web Search 2', description: 'Advanced web search capabilities for comprehensive results.', },
  ]);
}

export async function getAvailableSemanticSearchDefinitions(): Promise<SemanticSearchDefinitionResponse[]> {
  // return apiFetch<SemanticSearchDefinitionResponse[]>(`${DEF_BASE_PATH}/semantic-searches`);
  // Stub response until backend is implemented
  return Promise.resolve([
    { id: 'semantic-search-1', name: 'Semantic Search 1', description: 'Enables semantic search across large document sets.', },
    { id: 'semantic-search-2', name: 'Semantic Search 2', description: 'Advanced semantic search for precise information retrieval.', },
  ]);
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
