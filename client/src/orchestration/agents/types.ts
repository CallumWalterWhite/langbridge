export type LLMProvider = 'openai' | 'anthropic' | 'azure';

export interface LLMConnection {
  id: string;
  name: string;
  provider: LLMProvider;
  model: string;
  description?: string | null;
  configuration?: Record<string, unknown> | null;
  isActive: boolean;
  organizationId?: string | null;
  projectId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface LLMConnectionApiResponse {
  id: string;
  name: string;
  provider: LLMProvider;
  model: string;
  description?: string | null;
  configuration?: Record<string, unknown> | null;
  is_active: boolean;
  organization_id?: string | null;
  project_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateLLMConnectionPayload {
  name: string;
  provider: LLMProvider;
  model: string;
  apiKey: string;
  description?: string;
  configuration?: Record<string, unknown>;
  organizationId?: string;
  projectId?: string;
}

export interface TestLLMConnectionPayload {
  provider: LLMProvider;
  apiKey: string;
  model: string;
  configuration?: Record<string, unknown>;
}

export interface LLMConnectionTestResult {
  success: boolean;
  message?: string;
  [key: string]: unknown;
}

export interface UpdateLLMConnectionPayload {
  name: string;
  apiKey: string;
  model: string;
  configuration: Record<string, unknown>;
  isActive: boolean;
  description?: string;
  organizationId?: string | null;
  projectId?: string | null;
}
