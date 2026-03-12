'use client';

import { JSX, use, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { LucideIcon } from 'lucide-react';
import { ArrowRight, Bot, Database, Globe, Network, Plus, RefreshCw, Shield, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { formatRelativeDate } from '@/lib/utils';
import { deleteAgentDefinition, fetchAgentDefinitions, fetchLLMConnections } from '@/orchestration/agents';
import type { AgentDefinition, LLMConnection } from '@/orchestration/agents';

type AgentDefinitionsPageProps = {
  params: Promise<{ organizationId: string }>;
};

type ToolKind = 'sql' | 'web' | 'doc' | 'other';

type AgentDefinitionSummary = {
  analyticalSummary: string;
  promptSummary: string | null;
  assetSummary: string;
  executionSummary: string;
  capabilitySummary: string;
  assetTags: string[];
  capabilityTags: string[];
  hasFederatedAccess: boolean;
  hasResearchAccess: boolean;
  hasVisualization: boolean;
  scopedAssetCount: number;
  responseModeLabel: string;
  outputFormatLabel: string;
};

type DecoratedAgentDefinition = AgentDefinition & {
  summary: AgentDefinitionSummary;
};

const RESPONSE_MODE_LABELS: Record<string, string> = {
  analyst: 'Analyst',
  chat: 'Chat',
  executive: 'Executive brief',
  explainer: 'Explainer',
};

const OUTPUT_FORMAT_LABELS: Record<string, string> = {
  text: 'Text',
  markdown: 'Markdown',
  json: 'JSON',
  yaml: 'YAML',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function toRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function toArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function toStringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function toStringArray(value: unknown): string[] {
  return toArray(value)
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}

function toNumberValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function toBooleanValue(value: unknown): boolean {
  return value === true;
}

function normalizeToken(value: string): string {
  return value.trim().toLowerCase();
}

function humanizeValue(value: string): string {
  const normalized = value.replace(/[_-]+/g, ' ').trim();
  if (!normalized) {
    return 'Unknown';
  }
  return normalized
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function capitalizeFirst(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function joinPhrases(values: string[]): string {
  if (values.length === 0) {
    return '';
  }
  if (values.length === 1) {
    return values[0];
  }
  if (values.length === 2) {
    return `${values[0]} and ${values[1]}`;
  }
  return `${values.slice(0, -1).join(', ')}, and ${values[values.length - 1]}`;
}

function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function truncateText(value: string, maxLength = 160): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3).trimEnd()}...`;
}

function uniqueStrings(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function limitTags(values: string[], max = 4): string[] {
  const unique = uniqueStrings(values);
  if (unique.length <= max) {
    return unique;
  }
  return [...unique.slice(0, max - 1), `+${unique.length - (max - 1)} more`];
}

function resolveToolKind(toolType: unknown, name: string): ToolKind {
  if (toolType === 'sql' || toolType === 'web' || toolType === 'doc') {
    return toolType;
  }

  const normalizedName = normalizeToken(name);
  if (normalizedName.includes('sql')) {
    return 'sql';
  }
  if (normalizedName.includes('web')) {
    return 'web';
  }
  if (
    normalizedName.includes('doc') ||
    normalizedName.includes('file') ||
    normalizedName.includes('retriever') ||
    normalizedName.includes('semantic')
  ) {
    return 'doc';
  }
  return 'other';
}

function summarizeDefinition(definition: unknown): AgentDefinitionSummary {
  const payload = toRecord(definition);
  const prompt = toRecord(payload.prompt);
  const tools = toArray(payload.tools).map((tool) => {
    const record = toRecord(tool);
    const name = toStringValue(record.name);
    const config = toRecord(record.config);

    return {
      kind: resolveToolKind(record.tool_type, name),
      name,
      definitionName: toStringValue(config.definition_name),
      datasetIds: toStringArray(config.dataset_ids),
      semanticModelIds: toStringArray(config.semantic_model_ids),
    };
  });
  const features = toRecord(payload.features);
  const accessPolicy = toRecord(payload.access_policy);
  const execution = toRecord(payload.execution);
  const output = toRecord(payload.output);
  const guardrails = toRecord(payload.guardrails);
  const memory = toRecord(payload.memory);

  const sqlTools = tools.filter((tool) => tool.kind === 'sql');
  const docTools = tools.filter((tool) => tool.kind === 'doc');
  const webTools = tools.filter((tool) => tool.kind === 'web');

  const datasetBindingCount = sqlTools.reduce((total, tool) => total + tool.datasetIds.length, 0);
  const semanticBindingCount = sqlTools.reduce((total, tool) => total + tool.semanticModelIds.length, 0);
  const documentAssets = uniqueStrings(docTools.map((tool) => tool.definitionName));
  const responseMode = toStringValue(execution.response_mode) || 'analyst';
  const outputFormat = toStringValue(output.format) || 'text';
  const responseModeLabel = RESPONSE_MODE_LABELS[responseMode] ?? humanizeValue(responseMode);
  const outputFormatLabel = OUTPUT_FORMAT_LABELS[outputFormat] ?? humanizeValue(outputFormat);
  const hasVisualization = toBooleanValue(features.visualization_enabled);
  const hasResearchAccess =
    docTools.length > 0 || webTools.length > 0 || toBooleanValue(features.deep_research_enabled);
  const hasFederatedAccess = sqlTools.length > 0;

  const analyticalSegments: string[] = [];
  if (sqlTools.length > 0) {
    if (datasetBindingCount > 0) analyticalSegments.push(`queries ${pluralize(datasetBindingCount, 'dataset')}`);
    if (semanticBindingCount > 0) analyticalSegments.push(`uses ${pluralize(semanticBindingCount, 'governed semantic model')}`);
    if (datasetBindingCount === 0 && semanticBindingCount === 0) analyticalSegments.push('queries federated analytical assets');
  }
  if (documentAssets.length > 0) {
    analyticalSegments.push(`uses ${pluralize(documentAssets.length, 'document retriever')}`);
  } else if (docTools.length > 0) {
    analyticalSegments.push(`uses ${pluralize(docTools.length, 'document retrieval path')}`);
  }
  if (webTools.length > 0) {
    analyticalSegments.push(webTools.length === 1 ? 'adds public web research' : `adds ${pluralize(webTools.length, 'web research path')}`);
  }
  if (hasVisualization) {
    analyticalSegments.push('returns chart-ready output');
  }

  const assetSegments: string[] = [];
  if (sqlTools.length > 0) {
    if (datasetBindingCount > 0) assetSegments.push(pluralize(datasetBindingCount, 'scoped dataset'));
    if (semanticBindingCount > 0) assetSegments.push(pluralize(semanticBindingCount, 'scoped semantic model'));
    if (datasetBindingCount === 0 && semanticBindingCount === 0) assetSegments.push('Federated analytical access');
  }
  if (docTools.length > 0) {
    assetSegments.push(
      documentAssets.length > 0
        ? pluralize(documentAssets.length, 'named retriever')
        : pluralize(docTools.length, 'document retrieval path'),
    );
  }
  if (webTools.length > 0) {
    assetSegments.push(webTools.length === 1 ? 'Web research enabled' : pluralize(webTools.length, 'web research path'));
  }

  const executionMode = toStringValue(execution.mode) || 'single_step';
  const executionParts = [executionMode === 'iterative' ? 'Iterative reasoning' : 'Single-step execution'];
  const maxIterations = toNumberValue(execution.max_iterations);
  const maxStepsPerIteration = toNumberValue(execution.max_steps_per_iteration);
  if (executionMode === 'iterative' && maxIterations !== null) {
    executionParts.push(`${maxIterations} iterations`);
  }
  if (executionMode === 'iterative' && maxStepsPerIteration !== null) {
    executionParts.push(`${maxStepsPerIteration} steps per iteration`);
  }
  executionParts.push(`${responseModeLabel.toLowerCase()} responses`);
  executionParts.push(`${outputFormatLabel.toLowerCase()} output`);
  if (toBooleanValue(execution.allow_parallel_tools)) {
    executionParts.push('parallel tools enabled');
  }

  const capabilitySegments: string[] = [];
  const capabilityTags: string[] = [];
  if (hasVisualization) {
    capabilitySegments.push('visualizations enabled');
    capabilityTags.push('Visualization');
  }
  if (toBooleanValue(features.bi_copilot_enabled)) {
    capabilitySegments.push('BI copilots enabled');
    capabilityTags.push('BI copilot');
  }
  if (toBooleanValue(features.deep_research_enabled)) {
    capabilitySegments.push('deep research enabled');
    capabilityTags.push('Deep research');
  }
  if (toBooleanValue(features.mcp_enabled)) {
    capabilitySegments.push('MCP enabled');
    capabilityTags.push('MCP');
  }
  if (toBooleanValue(guardrails.moderation_enabled)) {
    capabilitySegments.push('moderation enabled');
    capabilityTags.push('Moderation');
  }
  if (toBooleanValue(execution.allow_parallel_tools)) {
    capabilityTags.push('Parallel tools');
  }
  if (toStringValue(memory.strategy)) {
    capabilitySegments.push(`${humanizeValue(toStringValue(memory.strategy)).toLowerCase()} memory`);
    capabilityTags.push(`${humanizeValue(toStringValue(memory.strategy))} memory`);
  }
  if (toArray(accessPolicy.allowed_connectors).length > 0 || toArray(accessPolicy.denied_connectors).length > 0) {
    capabilityTags.push('Connector policy');
  }
  if (toStringValue(accessPolicy.row_level_filter)) {
    capabilityTags.push('Row filters');
  }
  if (toStringValue(accessPolicy.pii_handling)) {
    capabilityTags.push('PII policy');
  }

  const promptSummarySource =
    toStringValue(prompt.user_instructions) ||
    toStringValue(prompt.system_prompt) ||
    toStringValue(prompt.style_guidance);

  const assetTags = limitTags([
    ...(datasetBindingCount > 0 ? [pluralize(datasetBindingCount, 'dataset')] : []),
    ...(semanticBindingCount > 0 ? [pluralize(semanticBindingCount, 'semantic model')] : []),
    ...documentAssets,
    ...(sqlTools.length > 0 && datasetBindingCount === 0 && semanticBindingCount === 0 ? ['Federated analytical access'] : []),
    ...(docTools.length > 0 && documentAssets.length === 0 ? ['Document retrieval'] : []),
    ...(webTools.length > 0 ? ['Web research'] : []),
  ]);

  return {
    analyticalSummary: analyticalSegments.length
      ? `${capitalizeFirst(joinPhrases(analyticalSegments))}.`
      : 'No semantic, retrieval, or research assets are stored in this definition yet.',
    promptSummary: promptSummarySource ? truncateText(promptSummarySource) : null,
    assetSummary: assetSegments.length ? `${capitalizeFirst(joinPhrases(assetSegments))}.` : 'No analytical assets configured.',
    executionSummary: `${capitalizeFirst(joinPhrases(executionParts))}.`,
    capabilitySummary: capabilitySegments.length
      ? `${capitalizeFirst(joinPhrases(capabilitySegments))}.`
      : 'Standard runtime and safety settings.',
    assetTags,
    capabilityTags: limitTags(capabilityTags),
    hasFederatedAccess,
    hasResearchAccess,
    hasVisualization,
    scopedAssetCount: datasetBindingCount + semanticBindingCount + documentAssets.length,
    responseModeLabel,
    outputFormatLabel,
  };
}

type OverviewCardProps = {
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
};

function OverviewCard({ icon: Icon, label, value, detail }: OverviewCardProps): JSX.Element {
  return (
    <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">{label}</p>
          <p className="text-2xl font-semibold text-[color:var(--text-primary)]">{value}</p>
          <p className="text-xs text-[color:var(--text-muted)]">{detail}</p>
        </div>
        <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[color:var(--chip-bg)] text-[color:var(--text-primary)]">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>
    </div>
  );
}

type DetailPanelProps = {
  icon: LucideIcon;
  title: string;
  summary: string;
  tags: string[];
};

function DetailPanel({ icon: Icon, title, summary, tags }: DetailPanelProps): JSX.Element {
  return (
    <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-xl bg-[color:var(--chip-bg)] text-[color:var(--text-primary)]">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">{title}</p>
            <p className="text-sm text-[color:var(--text-secondary)]">{summary}</p>
          </div>
          {tags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <Badge key={tag} variant="secondary" className="font-medium">
                  {tag}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function AgentDefinitionsPage({ params }: AgentDefinitionsPageProps): JSX.Element {
  const { organizationId } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  const definitionsQuery = useQuery<AgentDefinition[]>({
    queryKey: ['agent-definitions', organizationId],
    queryFn: () => fetchAgentDefinitions(organizationId),
  });

  const connectionsQuery = useQuery<LLMConnection[]>({
    queryKey: ['llm-connections', organizationId],
    queryFn: () => fetchLLMConnections(organizationId),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAgentDefinition(organizationId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-definitions', organizationId] });
      toast({ title: 'Agent deleted' });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Unable to delete agent right now.';
      toast({ title: 'Delete failed', description: message, variant: 'destructive' });
    },
  });

  const connectionLookup = useMemo(() => {
    return Object.fromEntries((connectionsQuery.data ?? []).map((connection) => [connection.id, connection]));
  }, [connectionsQuery.data]);

  const definitions = useMemo<DecoratedAgentDefinition[]>(() => {
    return (definitionsQuery.data ?? [])
      .slice()
      .sort((a, b) => {
        const left = a.updatedAt ?? a.createdAt ?? '';
        const right = b.updatedAt ?? b.createdAt ?? '';
        return left < right ? 1 : left > right ? -1 : 0;
      })
      .map((agent) => ({
        ...agent,
        summary: summarizeDefinition(agent.definition),
      }));
  }, [definitionsQuery.data]);

  const overview = useMemo(() => {
    return {
      total: definitions.length,
      federated: definitions.filter((agent) => agent.summary.hasFederatedAccess).length,
      governedAssets: definitions.reduce((total, agent) => total + agent.summary.scopedAssetCount, 0),
      researchOrVisual: definitions.filter((agent) => agent.summary.hasResearchAccess || agent.summary.hasVisualization).length,
    };
  }, [definitions]);

  const handleDelete = (id: string) => {
    if (deleteMutation.isPending) {
      return;
    }
    const confirmed = window.confirm('Delete this agent definition?');
    if (!confirmed) {
      return;
    }
    deleteMutation.mutate(id);
  };

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                Analytical agents
              </p>
              <div className="space-y-2">
                <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
                  Dataset-first agent definitions
                </h1>
                <p className="max-w-3xl text-sm md:text-base">
                  Organize agents around governed datasets, semantic models, and federated query paths instead of generic
                  prompt bundles. Each definition summarizes the analytical assets it can reach, how it executes, and
                  what kind of answer it is built to return.
                </p>
              </div>
            </div>
            <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-end">
              <Button onClick={() => router.push(`/agents/${organizationId}/definitions/create`)} size="sm" className="gap-2">
                <Plus className="h-4 w-4" aria-hidden="true" />
                New analytical agent
              </Button>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <OverviewCard
              icon={Bot}
              label="Definitions"
              value={String(overview.total)}
              detail="Analytical runtimes currently stored in this workspace."
            />
            <OverviewCard
              icon={Network}
              label="Federated access"
              value={String(overview.federated)}
              detail="Agents with analytical routes that execute through the federated path."
            />
            <OverviewCard
              icon={Database}
              label="Governed assets"
              value={String(overview.governedAssets)}
              detail="Scoped datasets, semantic models, or retrievers referenced by definitions."
            />
            <OverviewCard
              icon={Globe}
              label="Research or visuals"
              value={String(overview.researchOrVisual)}
              detail="Agents combining research inputs or visualization outputs."
            />
          </div>
        </div>
      </header>

      <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Definitions</h2>
            <p className="text-xs text-[color:var(--text-muted)]">
              Each card highlights governed analytical assets, execution profile, and runtime connection.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              definitionsQuery.refetch();
              connectionsQuery.refetch();
            }}
            disabled={definitionsQuery.isFetching || connectionsQuery.isFetching}
            className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
          >
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
          </Button>
        </div>

        <div className="mt-6 flex-1">
          {definitionsQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5"
                >
                  <Skeleton className="h-5 w-56" />
                  <Skeleton className="mt-4 h-4 w-full" />
                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <Skeleton className="h-28 w-full rounded-2xl" />
                    <Skeleton className="h-28 w-full rounded-2xl" />
                    <Skeleton className="h-28 w-full rounded-2xl" />
                  </div>
                </div>
              ))}
            </div>
          ) : definitionsQuery.isError ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <p className="text-sm">We couldn&apos;t load agent definitions right now.</p>
              <Button onClick={() => definitionsQuery.refetch()} variant="outline" size="sm">
                Try again
              </Button>
            </div>
          ) : definitions.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                No analytical agents yet
              </div>
              <div className="space-y-2">
                <p className="text-base font-semibold text-[color:var(--text-primary)]">
                  Create your first dataset-first analyst
                </p>
                <p className="max-w-xl text-sm">
                  Start with governed semantic access, federated data paths, and response settings that match how your
                  workspace answers analytical questions.
                </p>
              </div>
              <Button onClick={() => router.push(`/agents/${organizationId}/definitions/create`)} size="sm" className="gap-2">
                <Plus className="h-4 w-4" aria-hidden="true" />
                Build an analytical agent
              </Button>
            </div>
          ) : (
            <ul className="space-y-4">
              {definitions.map((agent) => {
                const connection = connectionLookup[agent.llmConnectionId];
                const updatedLabel = formatRelativeDate(agent.updatedAt ?? agent.createdAt ?? new Date().toISOString());

                return (
                  <li key={agent.id} className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5">
                    <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0 flex-1 space-y-4">
                        <div className="flex items-start gap-3">
                          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[color:var(--chip-bg)] text-[color:var(--text-primary)]">
                            <Bot className="h-5 w-5" aria-hidden="true" />
                          </span>
                          <div className="min-w-0 flex-1 space-y-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-base font-semibold text-[color:var(--text-primary)]">{agent.name}</p>
                              <Badge variant={agent.isActive ? 'success' : 'secondary'}>
                                {agent.isActive ? 'Active' : 'Inactive'}
                              </Badge>
                              <Badge variant="secondary">{agent.summary.responseModeLabel}</Badge>
                              <Badge variant="secondary">{agent.summary.outputFormatLabel}</Badge>
                            </div>
                            <p className="text-sm text-[color:var(--text-secondary)]">
                              {agent.description || agent.summary.promptSummary || 'No description provided.'}
                            </p>
                            <p className="text-xs text-[color:var(--text-muted)]">{agent.summary.analyticalSummary}</p>
                          </div>
                        </div>

                        <div className="grid gap-3 lg:grid-cols-3">
                          <DetailPanel
                            icon={Database}
                            title="Analytical assets"
                            summary={agent.summary.assetSummary}
                            tags={agent.summary.assetTags}
                          />
                          <DetailPanel
                            icon={Network}
                            title="Execution profile"
                            summary={agent.summary.executionSummary}
                            tags={[agent.summary.responseModeLabel, agent.summary.outputFormatLabel]}
                          />
                          <DetailPanel
                            icon={Shield}
                            title="Capabilities"
                            summary={agent.summary.capabilitySummary}
                            tags={agent.summary.capabilityTags}
                          />
                        </div>
                      </div>

                      <div className="flex w-full flex-col gap-3 xl:w-72 xl:items-stretch">
                        <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
                            Runtime connection
                          </p>
                          <div className="mt-2 space-y-1">
                            <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                              {connection?.name ?? agent.llmConnectionId}
                            </p>
                            <p className="text-xs text-[color:var(--text-muted)]">
                              {connection ? `${humanizeValue(connection.provider)} / ${connection.model}` : 'Connection metadata unavailable'}
                            </p>
                            <p className="text-xs text-[color:var(--text-muted)]">
                              {updatedLabel ? `Updated ${updatedLabel}` : 'Update timestamp unavailable'}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center justify-between gap-3">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/agents/${organizationId}/definitions/${agent.id}`)}
                            className="gap-2"
                          >
                            Edit <ArrowRight className="h-4 w-4" aria-hidden="true" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(agent.id)}
                            disabled={deleteMutation.isPending}
                            aria-label="Delete agent"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
