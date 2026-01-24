import { apiFetch } from '../http';

const BASE_PATH = '/api/v1/thread';

function requireOrganizationId(organizationId: string): string {
  if (!organizationId) {
    throw new Error('Organization id is required.');
  }
  return organizationId;
}

function basePath(organizationId: string): string {
  return `${BASE_PATH}/${requireOrganizationId(organizationId)}`;
}

export type Thread = {
  id: string;
  projectId: string | null;
  title: string | null;
  status: string;
  metadataJson: Record<string, unknown> | null;
  createdAt: string | null;
  updatedAt: string | null;
};

export type ThreadListResponse = {
  threads: Thread[];
};

export type ThreadCreatePayload = {
  projectId?: string;
  title?: string;
  metadataJson?: Record<string, unknown>;
};

export type ThreadUpdatePayload = {
  title?: string;
  metadataJson?: Record<string, unknown>;
};

export type ThreadTabularResult = {
  columns: string[];
  rows: Array<Record<string, unknown> | unknown[]>;
  rowCount?: number | null;
  elapsedMs?: number | null;
};

export type ThreadVisualizationSpec = {
  chartType?: string | null;
  x?: string | null;
  y?: string | string[] | null;
  groupBy?: string | null;
  title?: string | null;
  options?: Record<string, unknown> | null;
};

export type ThreadChatResponse = {
  result: ThreadTabularResult | null;
  visualization: ThreadVisualizationSpec | null;
  summary: string | null;
};

export type ThreadMessage = {
  id: string;
  threadId: string;
  parentMessageId?: string | null;
  role: 'system' | 'user' | 'assistant' | 'tool' | string;
  content: Record<string, unknown>;
  modelSnapshot?: Record<string, unknown> | null;
  tokenUsage?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  createdAt?: string | null;
};

export type ThreadHistoryResponse = {
  messages: ThreadMessage[];
};

export async function listThreads(organizationId: string): Promise<Thread[]> {
  const response = await apiFetch<ThreadListResponse>(`${basePath(organizationId)}/`);
  return response.threads;
}

export async function createThread(
  organizationId: string,
  payload: ThreadCreatePayload = {},
): Promise<Thread> {
  return apiFetch<Thread>(`${basePath(organizationId)}/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteThread(organizationId: string, threadId: string): Promise<void> {
  await apiFetch<void>(`${basePath(organizationId)}/${threadId}`, { method: 'DELETE', skipJsonParse: true });
}

export async function fetchThread(organizationId: string, threadId: string): Promise<Thread> {
  return apiFetch<Thread>(`${basePath(organizationId)}/${threadId}`);
}

export async function updateThread(
  organizationId: string,
  threadId: string,
  payload: ThreadUpdatePayload,
): Promise<Thread> {
  const body: Record<string, unknown> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.metadataJson !== undefined) body.metadata_json = payload.metadataJson;

  return apiFetch<Thread>(`${basePath(organizationId)}/${threadId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export async function listThreadMessages(organizationId: string, threadId: string): Promise<ThreadMessage[]> {
  const response = await apiFetch<ThreadHistoryResponse>(`${basePath(organizationId)}/${threadId}/messages`);
  return response.messages;
}

export async function runThreadChat(
  organizationId: string,
  threadId: string,
  message: string,
  agentId: string,
): Promise<ThreadChatResponse> {
  const body: Record<string, unknown> = { message, agent_id: agentId };
  return apiFetch<ThreadChatResponse>(`${basePath(organizationId)}/${threadId}/chat`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
