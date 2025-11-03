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
  await apiFetch<void>(`${BASE_PATH}/${threadId}`, { method: 'DELETE' });
}

export async function runThreadChat(threadId: string, message: string): Promise<ThreadChatResponse> {
  return apiFetch<ThreadChatResponse>(`${BASE_PATH}/${threadId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}
