import { apiFetch } from '../http';

const BASE_PATH = '/api/v1/thread';

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

export async function listThreads(): Promise<Thread[]> {
  const response = await apiFetch<ThreadListResponse>(`${BASE_PATH}/`);
  return response.threads;
}

export async function createThread(payload: ThreadCreatePayload = {}): Promise<Thread> {
  return apiFetch<Thread>(`${BASE_PATH}/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteThread(threadId: string): Promise<void> {
  await apiFetch<void>(`${BASE_PATH}/${threadId}`, { method: 'DELETE', skipJsonParse: true });
}

export async function fetchThread(threadId: string): Promise<Thread> {
  return apiFetch<Thread>(`${BASE_PATH}/${threadId}`);
}

export async function updateThread(threadId: string, payload: ThreadUpdatePayload): Promise<Thread> {
  const body: Record<string, unknown> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.metadataJson !== undefined) body.metadata_json = payload.metadataJson;

  return apiFetch<Thread>(`${BASE_PATH}/${threadId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export async function listThreadMessages(threadId: string): Promise<ThreadMessage[]> {
  const response = await apiFetch<ThreadHistoryResponse>(`${BASE_PATH}/${threadId}/messages`);
  return response.messages;
}

export async function runThreadChat(
  threadId: string,
  message: string,
  agentId: string,
): Promise<ThreadChatResponse> {
  const body: Record<string, unknown> = { message, agent_id: agentId };
  return apiFetch<ThreadChatResponse>(`${BASE_PATH}/${threadId}/chat`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
