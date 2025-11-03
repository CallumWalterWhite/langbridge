import { apiFetch } from '../http';

export type ThreadTabularResult = {
  columns: string[];
  rows: unknown[][];
  rowcount?: number | null;
  elapsed_ms?: number | null;
};

export type ThreadVisualizationSpec = {
  chart_type: string;
  x?: string;
  y?: string | string[];
  group_by?: string;
  title?: string;
  options?: Record<string, unknown>;
};

export type ThreadChatResponse = {
  result: ThreadTabularResult | null;
  visualization: ThreadVisualizationSpec | null;
  summary: string | null;
};

export async function runThreadChat(message: string): Promise<ThreadChatResponse> {
  return apiFetch<ThreadChatResponse>('/api/v1/thread/', {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

