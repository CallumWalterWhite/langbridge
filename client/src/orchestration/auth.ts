import { apiFetch } from './http';

export type SessionUser = {
  sub: string;
  username: string;
  name?: string;
  avatar_url?: string;
  email?: string;
  provider: string;
};

export type SessionResponse = {
  user: SessionUser;
};

export async function fetchSession(): Promise<SessionResponse> {
  return apiFetch<SessionResponse>('/api/v1/auth/me');
}

export async function logout(): Promise<void> {
  await apiFetch('/api/v1/auth/logout');
}
