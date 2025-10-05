import type { ChatMessage, ChatMessagePair, ChatSession, ChatSessionResponse } from './types';
import { apiFetch } from '../http';

const BASE_PATH = '/api/v1/chat';

interface MeResponse {
  user: {
    sub: string;
    username: string;
    name?: string;
    avatar_url?: string;
    email?: string;
    provider: string;
  };
}

export async function checkAuth(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/api/v1/auth/me');
}

export async function listChatSessions(): Promise<ChatSession[]> {
  return apiFetch<ChatSession[]>(`${BASE_PATH}/sessions`);
}

export async function createChatSession(): Promise<ChatSessionResponse> {
  return apiFetch<ChatSessionResponse>(`${BASE_PATH}/sessions`, {
    method: 'POST',
  });
}

export async function listChatMessages(sessionId: string): Promise<ChatMessage[]> {
  return apiFetch<ChatMessage[]>(`${BASE_PATH}/sessions/${sessionId}/messages`);
}

export async function createChatMessage(sessionId: string, content: string): Promise<ChatMessagePair> {
  return apiFetch<ChatMessagePair>(`${BASE_PATH}/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export type { ChatMessage, ChatMessagePair, ChatSession, ChatSessionResponse };
