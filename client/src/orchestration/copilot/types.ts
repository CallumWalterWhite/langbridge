import type { SemanticQueryPayload, SemanticQueryResponse } from '@/orchestration/semanticQuery/types';

export interface QueryBuilderContextPayload {
  summary?: string;
  focus?: string;
  timezone?: string;
}

export interface QueryBuilderCopilotRequestPayload {
  organizationId: string;
  projectId?: string | null;
  semanticModelId: string;
  instructions: string;
  builderState: SemanticQueryPayload;
  conversationContext?: string | null;
  generatePreview?: boolean;
  context?: QueryBuilderContextPayload;
}

export interface QueryBuilderCopilotResponsePayload {
  updatedQuery: SemanticQueryPayload;
  actions: string[];
  explanation?: string | null;
  preview?: SemanticQueryResponse;
  rawModelResponse?: string | null;
}

export interface DashboardCopilotAssistRequestPayload {
  projectId?: string | null;
  semanticModelId: string;
  instructions: string;
  dashboardName?: string | null;
  currentDashboard?: Record<string, unknown> | null;
  generatePreviews?: boolean;
  maxWidgets?: number;
}

export interface DashboardCopilotJobResponsePayload {
  jobId: string;
  jobStatus: string;
}
