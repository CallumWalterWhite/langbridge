'use client';

import { JSX, useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import type { FormEvent } from 'react';
import { Bot, Database, FileText, Globe, Layers3, Network, Sparkles, Trash2 } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { cn } from '@/lib/utils';
import {
  createAgentDefinition,
  deleteAgentDefinition,
  fetchAgentDefinition,
  fetchLLMConnections,
  getAvailableFileRetriverDefinitions,
  getAvailableSemanticModels,
  updateAgentDefinition,
} from '@/orchestration/agents';
import type {
  AgentDefinition,
  CreateAgentDefinitionPayload,
  FileRetriverDefinitionResponse,
  LLMConnection,
  SemanticModelResponse,
  UpdateAgentDefinitionPayload,
} from '@/orchestration/agents';
import { fetchDatasetCatalog } from '@/orchestration/datasets';
import type { DatasetCatalogItem, DatasetCatalogResponse } from '@/orchestration/datasets';
import { ApiError } from '@/orchestration/http';

const memoryStrategies = ['database'] as const;
const executionModes = ['single_step', 'iterative'] as const;
const responseModes = ['analyst', 'chat', 'executive', 'explainer'] as const;
const outputFormats = ['text', 'markdown', 'json', 'yaml'] as const;

const responseModeLabels: Record<(typeof responseModes)[number], string> = {
  analyst: 'Analyst (federated analysis)',
  chat: 'Chat (conversation only)',
  executive: 'Executive brief',
  explainer: 'Plain-language explainer',
};

type AnalyticalRoute = 'dataset' | 'semantic_model';

enum ToolType {
  sql = 'sql',
  web = 'web',
  doc = 'doc',
}

interface ToolState {
  toolType: ToolType;
  name: string;
  description: string;
  analyticalRoute: AnalyticalRoute;
  datasetIds: string[];
  semanticModelIds: string[];
  config: string;
}

interface FormState {
  name: string;
  description: string;
  llmConnectionId: string;
  isActive: boolean;
  biCopilotEnabled: boolean;
  deepResearchEnabled: boolean;
  visualizationEnabled: boolean;
  mcpEnabled: boolean;
  systemPrompt: string;
  userInstructions: string;
  styleGuidance: string;
  memoryStrategy: (typeof memoryStrategies)[number];
  ttlSeconds: string;
  vectorIndex: string;
  databaseTable: string;
  tools: ToolState[];
  allowedConnectors: string;
  deniedConnectors: string;
  piiHandling: string;
  rowLevelFilter: string;
  executionMode: (typeof executionModes)[number];
  responseMode: (typeof responseModes)[number];
  maxIterations: string;
  maxStepsPerIteration: string;
  allowParallelTools: boolean;
  outputFormat: (typeof outputFormats)[number];
  jsonSchema: string;
  markdownTemplate: string;
  moderationEnabled: boolean;
  blockedCategories: string;
  regexDenylist: string;
  escalationMessage: string;
  emitTraces: boolean;
  capturePrompts: boolean;
  auditFields: string;
}

interface ToolDefinitionOption {
  id: string;
  name: string;
  description: string;
}

interface AgentDefinitionFormProps {
  mode: 'create' | 'edit';
  agentId?: string;
  organizationId: string;
  initialAgent?: AgentDefinition | null;
  onComplete?: () => void;
}

const TOOL_DEFAULTS: Record<ToolType, Pick<ToolState, 'name' | 'description' | 'config' | 'analyticalRoute' | 'datasetIds' | 'semanticModelIds'>> = {
  [ToolType.sql]: {
    name: 'federated_analyst',
    description: 'Reason over analytical assets through the federated dataset execution path.',
    analyticalRoute: 'dataset',
    datasetIds: [],
    semanticModelIds: [],
    config: '{}',
  },
  [ToolType.web]: {
    name: 'web_research',
    description: 'Search the public web for supporting context and current sources.',
    analyticalRoute: 'dataset',
    datasetIds: [],
    semanticModelIds: [],
    config: '{\n  "max_results": 6,\n  "safe_search": "moderate"\n}',
  },
  [ToolType.doc]: {
    name: 'document_retrieval',
    description: 'Retrieve internal documents and knowledge definitions.',
    analyticalRoute: 'dataset',
    datasetIds: [],
    semanticModelIds: [],
    config: '{}',
  },
};

const TOOL_LABELS: Record<ToolType, string> = {
  [ToolType.sql]: 'Analyst route',
  [ToolType.web]: 'Web research',
  [ToolType.doc]: 'Document retrieval',
};

const TOOL_TONES: Record<ToolType, CSSProperties> = {
  [ToolType.sql]: {
    backgroundImage:
      'linear-gradient(135deg, rgba(14,165,233,0.16), rgba(16,185,129,0.12), transparent 72%), linear-gradient(180deg, var(--panel-bg), var(--panel-bg))',
  },
  [ToolType.web]: {
    backgroundImage:
      'linear-gradient(135deg, rgba(245,158,11,0.16), rgba(249,115,22,0.12), transparent 72%), linear-gradient(180deg, var(--panel-bg), var(--panel-bg))',
  },
  [ToolType.doc]: {
    backgroundImage:
      'linear-gradient(135deg, rgba(99,102,241,0.16), rgba(59,130,246,0.12), transparent 72%), linear-gradient(180deg, var(--panel-bg), var(--panel-bg))',
  },
};

const HERO_SECTION_STYLE: CSSProperties = {
  backgroundImage:
    'linear-gradient(135deg, rgba(125,211,252,0.16), rgba(16,185,129,0.12), transparent 76%), linear-gradient(180deg, var(--panel-bg), var(--panel-bg))',
};

function defaultFormState(): FormState {
  return {
    name: '',
    description: '',
    llmConnectionId: '',
    isActive: true,
    biCopilotEnabled: false,
    deepResearchEnabled: false,
    visualizationEnabled: false,
    mcpEnabled: false,
    systemPrompt: '',
    userInstructions: '',
    styleGuidance: '',
    memoryStrategy: 'database',
    ttlSeconds: '',
    vectorIndex: '',
    databaseTable: '',
    tools: [],
    allowedConnectors: '',
    deniedConnectors: '',
    piiHandling: '',
    rowLevelFilter: '',
    executionMode: 'single_step',
    responseMode: 'analyst',
    maxIterations: '3',
    maxStepsPerIteration: '5',
    allowParallelTools: false,
    outputFormat: 'text',
    jsonSchema: '',
    markdownTemplate: '',
    moderationEnabled: true,
    blockedCategories: '',
    regexDenylist: '',
    escalationMessage: '',
    emitTraces: true,
    capturePrompts: true,
    auditFields: '',
  };
}

function createToolState(toolType: ToolType): ToolState {
  return { toolType, ...TOOL_DEFAULTS[toolType] };
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function toArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function toStringValue(value: unknown, fallback = ''): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return fallback;
}

function toStringArray(value: unknown): string[] {
  return toArray(value).map((item) => toStringValue(item)).filter(Boolean);
}

function toBooleanValue(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function toCsvString(value: unknown): string {
  return toArray(value).filter((item): item is string => typeof item === 'string').join(', ');
}

function isOption<T extends string>(value: unknown, options: readonly T[]): value is T {
  return typeof value === 'string' && options.includes(value as T);
}

function uniqueStrings(values: string[]): string[] {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)));
}

function parseJsonSafe(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
}

function stringifyConfig(value: unknown): string {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

function readConfigField(config: string, key: string): string {
  const parsed = parseJsonSafe(config);
  if (!parsed || typeof parsed !== 'object') return '';
  const value = (parsed as Record<string, unknown>)[key];
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return '';
}

function listFromCsv(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function resolveToolType(value: unknown, name: string): ToolType {
  if (value === ToolType.web || value === ToolType.doc || value === ToolType.sql) return value;
  const normalized = name.trim().toLowerCase();
  if (normalized.includes('web')) return ToolType.web;
  if (normalized.includes('doc') || normalized.includes('file') || normalized.includes('retriever')) return ToolType.doc;
  return ToolType.sql;
}

function hydrateToolState(tool: unknown): ToolState {
  const record = toRecord(tool);
  const name = toStringValue(record.name);
  const toolType = resolveToolType(record.tool_type, name);
  const description = toStringValue(record.description);
  const config = toRecord(record.config);

  if (toolType === ToolType.sql) {
    const datasetIds = uniqueStrings(toStringArray(config.dataset_ids));
    const semanticModelIds = datasetIds.length
      ? []
      : uniqueStrings(toStringArray(config.semantic_model_ids).concat(config.definition_id ? [toStringValue(config.definition_id)] : []));
    return {
      ...createToolState(ToolType.sql),
      name: name || TOOL_DEFAULTS[ToolType.sql].name,
      description: description || TOOL_DEFAULTS[ToolType.sql].description,
      analyticalRoute: datasetIds.length ? 'dataset' : 'semantic_model',
      datasetIds,
      semanticModelIds,
      config: '{}',
    };
  }

  return {
    ...createToolState(toolType),
    name: name || TOOL_DEFAULTS[toolType].name,
    description: description || TOOL_DEFAULTS[toolType].description,
    config: stringifyConfig(config) || TOOL_DEFAULTS[toolType].config,
  };
}

function hydrateFromDefinition(definition: unknown, base: FormState): FormState {
  if (!definition || typeof definition !== 'object') return base;
  const payload = toRecord(definition);
  const prompt = toRecord(payload.prompt);
  const memory = toRecord(payload.memory);
  const tools = toArray(payload.tools);
  const accessPolicy = toRecord(payload.access_policy);
  const execution = toRecord(payload.execution);
  const output = toRecord(payload.output);
  const guardrails = toRecord(payload.guardrails);
  const observability = toRecord(payload.observability);
  const features = toRecord(payload.features);

  return {
    ...base,
    llmConnectionId: toStringValue(payload.llm_connection_id, base.llmConnectionId),
    biCopilotEnabled: toBooleanValue(features.bi_copilot_enabled, base.biCopilotEnabled),
    deepResearchEnabled: toBooleanValue(features.deep_research_enabled, base.deepResearchEnabled),
    visualizationEnabled: toBooleanValue(features.visualization_enabled, base.visualizationEnabled),
    mcpEnabled: toBooleanValue(features.mcp_enabled, base.mcpEnabled),
    systemPrompt: toStringValue(prompt.system_prompt),
    userInstructions: toStringValue(prompt.user_instructions),
    styleGuidance: toStringValue(prompt.style_guidance),
    memoryStrategy: isOption(memory.strategy, memoryStrategies) ? memory.strategy : base.memoryStrategy,
    ttlSeconds: memory.ttl_seconds == null ? '' : String(memory.ttl_seconds),
    vectorIndex: toStringValue(memory.vector_index),
    databaseTable: toStringValue(memory.database_table),
    tools: tools.length ? tools.map(hydrateToolState) : base.tools,
    allowedConnectors: toCsvString(accessPolicy.allowed_connectors),
    deniedConnectors: toCsvString(accessPolicy.denied_connectors),
    piiHandling: toStringValue(accessPolicy.pii_handling),
    rowLevelFilter: toStringValue(accessPolicy.row_level_filter),
    executionMode: isOption(execution.mode, executionModes) ? execution.mode : base.executionMode,
    responseMode: isOption(execution.response_mode, responseModes) ? execution.response_mode : base.responseMode,
    maxIterations: execution.max_iterations == null ? base.maxIterations : String(execution.max_iterations),
    maxStepsPerIteration:
      execution.max_steps_per_iteration == null ? base.maxStepsPerIteration : String(execution.max_steps_per_iteration),
    allowParallelTools: toBooleanValue(execution.allow_parallel_tools, base.allowParallelTools),
    outputFormat: isOption(output.format, outputFormats) ? output.format : base.outputFormat,
    jsonSchema: output.json_schema ? stringifyConfig(output.json_schema) : '',
    markdownTemplate: toStringValue(output.markdown_template),
    moderationEnabled: toBooleanValue(guardrails.moderation_enabled, base.moderationEnabled),
    blockedCategories: toCsvString(guardrails.blocked_categories),
    regexDenylist: toCsvString(guardrails.regex_denylist),
    escalationMessage: toStringValue(guardrails.escalation_message),
    emitTraces: toBooleanValue(observability.emit_traces, base.emitTraces),
    capturePrompts: toBooleanValue(observability.capture_prompts, base.capturePrompts),
    auditFields: toCsvString(observability.audit_fields),
  };
}

function ArchitectureLane({
  icon,
  title,
  description,
  stat,
}: {
  icon: JSX.Element;
  title: string;
  description: string;
  stat: string;
}): JSX.Element {
  return (
    <div className="surface-card rounded-[28px] p-4 shadow-soft">
      <div className="flex items-start justify-between gap-3">
        <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-[color:var(--chip-bg)] text-[color:var(--text-primary)]">
          {icon}
        </div>
        <Badge variant="secondary">{stat}</Badge>
      </div>
      <div className="mt-4 space-y-1">
        <p className="text-sm font-semibold text-[color:var(--text-primary)]">{title}</p>
        <p className="text-xs leading-5 text-[color:var(--text-muted)]">{description}</p>
      </div>
    </div>
  );
}

export function AgentDefinitionForm({
  mode,
  agentId,
  organizationId,
  initialAgent,
  onComplete,
}: AgentDefinitionFormProps): JSX.Element {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { selectedOrganizationId, selectedProjectId, selectedProject } = useWorkspaceScope();
  const scopeOrganizationId = organizationId || selectedOrganizationId;
  const [formState, setFormState] = useState<FormState>(defaultFormState());
  const [pending, setPending] = useState(false);

  const connectionsQuery = useQuery<LLMConnection[]>({
    queryKey: ['llm-connections', scopeOrganizationId],
    enabled: Boolean(scopeOrganizationId),
    queryFn: () => fetchLLMConnections(scopeOrganizationId),
  });

  const datasetsQuery = useQuery<DatasetCatalogResponse>({
    queryKey: ['dataset-catalog', scopeOrganizationId, selectedProjectId],
    enabled: Boolean(scopeOrganizationId),
    queryFn: () => fetchDatasetCatalog(scopeOrganizationId ?? '', selectedProjectId || undefined),
  });

  const semanticModelsQuery = useQuery<SemanticModelResponse[]>({
    queryKey: ['semantic-models', scopeOrganizationId, selectedProjectId],
    enabled: Boolean(scopeOrganizationId),
    queryFn: () => getAvailableSemanticModels(scopeOrganizationId ?? '', selectedProjectId || undefined),
  });

  const documentDefinitionsQuery = useQuery<ToolDefinitionOption[]>({
    queryKey: ['agent-doc-definitions'],
    queryFn: async () => {
      const retrievers: FileRetriverDefinitionResponse[] = await getAvailableFileRetriverDefinitions();
      return retrievers.map((retriever) => ({
        id: retriever.id,
        name: retriever.name,
        description: retriever.description ?? '',
      }));
    },
  });

  const agentDefinitionQuery = useQuery<AgentDefinition>({
    queryKey: ['agent-definition', scopeOrganizationId, agentId],
    enabled: mode === 'edit' && Boolean(agentId) && Boolean(scopeOrganizationId) && !initialAgent,
    queryFn: () => fetchAgentDefinition(scopeOrganizationId ?? '', agentId ?? ''),
  });

  useEffect(() => {
    if (initialAgent || !agentDefinitionQuery.data) return;
    const agent = agentDefinitionQuery.data;
    const base = defaultFormState();
    setFormState({
      ...hydrateFromDefinition(agent.definition, base),
      name: agent.name,
      description: agent.description ?? '',
      llmConnectionId: agent.llmConnectionId,
      isActive: agent.isActive,
    });
  }, [agentDefinitionQuery.data, initialAgent]);

  useEffect(() => {
    if (!initialAgent) return;
    const base = defaultFormState();
    setFormState({
      ...hydrateFromDefinition(initialAgent.definition, base),
      name: initialAgent.name,
      description: initialAgent.description ?? '',
      llmConnectionId: initialAgent.llmConnectionId,
      isActive: initialAgent.isActive,
    });
  }, [initialAgent]);

  useEffect(() => {
    const connections = connectionsQuery.data ?? [];
    if (!formState.llmConnectionId && connections.length > 0) {
      setFormState((prev) => ({ ...prev, llmConnectionId: connections[0].id }));
    }
  }, [connectionsQuery.data, formState.llmConnectionId]);

  const tools = formState.tools;
  const datasetOptions = useMemo(() => datasetsQuery.data?.items ?? [], [datasetsQuery.data]);
  const semanticModelOptions = useMemo(() => semanticModelsQuery.data ?? [], [semanticModelsQuery.data]);
  const documentDefinitionOptions = useMemo(
    () => documentDefinitionsQuery.data ?? [],
    [documentDefinitionsQuery.data],
  );
  const llmOptions = (connectionsQuery.data ?? []).filter((conn) =>
    scopeOrganizationId ? conn.organizationId === scopeOrganizationId || !conn.organizationId : true,
  );
  const scopeLabel = selectedProject ? `${selectedProject.name} project` : 'Organization scope';

  const connectionLookup = useMemo(
    () => Object.fromEntries((connectionsQuery.data ?? []).map((conn) => [conn.id, conn.name])),
    [connectionsQuery.data],
  );
  const datasetLookup = useMemo<Record<string, DatasetCatalogItem>>(
    () => Object.fromEntries(datasetOptions.map((dataset) => [dataset.id, dataset])),
    [datasetOptions],
  );
  const semanticModelLookup = useMemo<Record<string, SemanticModelResponse>>(
    () => Object.fromEntries(semanticModelOptions.map((model) => [model.id, model])),
    [semanticModelOptions],
  );
  const documentDefinitionLookup = useMemo<Record<string, ToolDefinitionOption>>(
    () => Object.fromEntries(documentDefinitionOptions.map((definition) => [definition.id, definition])),
    [documentDefinitionOptions],
  );

  const updateTool = (index: number, next: Partial<ToolState>) => {
    setFormState((prev) => {
      const nextTools = prev.tools.slice();
      nextTools[index] = { ...nextTools[index], ...next };
      return { ...prev, tools: nextTools };
    });
  };

  const updateToolConfig = (index: number, updates: Record<string, unknown>) => {
    setFormState((prev) => {
      const nextTools = prev.tools.slice();
      const currentConfig = parseJsonSafe(nextTools[index].config);
      const nextConfig: Record<string, unknown> =
        currentConfig && typeof currentConfig === 'object' ? { ...(currentConfig as Record<string, unknown>) } : {};
      Object.entries(updates).forEach(([key, value]) => {
        if (value === '' || value === undefined || value === null) delete nextConfig[key];
        else nextConfig[key] = value;
      });
      nextTools[index] = { ...nextTools[index], config: stringifyConfig(nextConfig) || '{}' };
      return { ...prev, tools: nextTools };
    });
  };

  const addTool = (toolType: ToolType) => {
    setFormState((prev) => ({ ...prev, tools: [...prev.tools, createToolState(toolType)] }));
  };

  const removeTool = (index: number) => {
    setFormState((prev) => ({ ...prev, tools: prev.tools.filter((_, toolIndex) => toolIndex !== index) }));
  };

  const setSqlRoute = (index: number, route: AnalyticalRoute) => {
    updateTool(index, {
      analyticalRoute: route,
      datasetIds: route === 'dataset' ? tools[index].datasetIds : [],
      semanticModelIds: route === 'semantic_model' ? tools[index].semanticModelIds : [],
    });
  };

  const toggleSqlAsset = (index: number, route: AnalyticalRoute, assetId: string) => {
    const current = tools[index];
    const selectedIds = route === 'dataset' ? current.datasetIds : current.semanticModelIds;
    const nextIds = selectedIds.includes(assetId)
      ? selectedIds.filter((candidateId) => candidateId !== assetId)
      : [...selectedIds, assetId];
    updateTool(index, {
      analyticalRoute: route,
      datasetIds: route === 'dataset' ? nextIds : [],
      semanticModelIds: route === 'semantic_model' ? nextIds : [],
    });
  };

  const validateSqlTool = (tool: ToolState, index: number): string | null => {
    const hasDatasets = uniqueStrings(tool.datasetIds).length > 0;
    const hasSemanticModels = uniqueStrings(tool.semanticModelIds).length > 0;
    return hasDatasets === hasSemanticModels
      ? `Analyst route ${index + 1} must target either datasets or semantic models.`
      : null;
  };

  const handleDelete = async () => {
    if (mode !== 'edit' || !agentId || !scopeOrganizationId) return;
    try {
      setPending(true);
      await deleteAgentDefinition(scopeOrganizationId, agentId);
      toast({ title: 'Agent deleted', description: 'Your agent definition has been deleted.' });
      queryClient.invalidateQueries({ queryKey: ['agent-definitions', scopeOrganizationId] });
      onComplete?.();
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'Unable to delete agent right now.';
      toast({ title: 'Delete failed', description: message, variant: 'destructive' });
    } finally {
      setPending(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!scopeOrganizationId) {
      toast({ title: 'Select an organization', variant: 'destructive' });
      return;
    }
    if (!formState.name.trim()) {
      toast({ title: 'Name is required', variant: 'destructive' });
      return;
    }
    if (!formState.llmConnectionId) {
      toast({ title: 'Select a connection', description: 'Choose an LLM connection for this agent.' });
      return;
    }

    for (const [index, tool] of tools.entries()) {
      if (!tool.name.trim()) {
        toast({ title: `Tool ${index + 1} needs a name`, variant: 'destructive' });
        return;
      }
      if (tool.toolType === ToolType.sql) {
        const validationError = validateSqlTool(tool, index);
        if (validationError) {
          toast({ title: 'Analytical route is incomplete', description: validationError, variant: 'destructive' });
          return;
        }
      }
    }

    const payloadDefinition = {
      prompt: {
        system_prompt: formState.systemPrompt,
        user_instructions: formState.userInstructions,
        style_guidance: formState.styleGuidance,
      },
      memory: {
        strategy: formState.memoryStrategy,
        ttl_seconds: formState.ttlSeconds ? Number(formState.ttlSeconds) : undefined,
        vector_index: formState.vectorIndex || undefined,
        database_table: formState.databaseTable || undefined,
      },
      tools: tools.map((tool) =>
        tool.toolType === ToolType.sql
          ? {
              name: tool.name.trim(),
              tool_type: tool.toolType,
              description: tool.description || undefined,
              config:
                tool.analyticalRoute === 'dataset'
                  ? { dataset_ids: uniqueStrings(tool.datasetIds) }
                  : { semantic_model_ids: uniqueStrings(tool.semanticModelIds) },
            }
          : {
              name: tool.name.trim(),
              tool_type: tool.toolType,
              description: tool.description || undefined,
              config: parseJsonSafe(tool.config),
            },
      ),
      features: {
        bi_copilot_enabled: formState.biCopilotEnabled,
        deep_research_enabled: formState.deepResearchEnabled,
        visualization_enabled: formState.visualizationEnabled,
        mcp_enabled: formState.mcpEnabled,
      },
      access_policy: {
        allowed_connectors: listFromCsv(formState.allowedConnectors),
        denied_connectors: listFromCsv(formState.deniedConnectors),
        pii_handling: formState.piiHandling || undefined,
        row_level_filter: formState.rowLevelFilter || undefined,
      },
      execution: {
        mode: formState.executionMode,
        response_mode: formState.responseMode,
        max_iterations: Number(formState.maxIterations || 3),
        max_steps_per_iteration: Number(formState.maxStepsPerIteration || 5),
        allow_parallel_tools: formState.allowParallelTools,
      },
      output: {
        format: formState.outputFormat,
        json_schema: formState.jsonSchema ? parseJsonSafe(formState.jsonSchema) : undefined,
        markdown_template: formState.markdownTemplate || undefined,
      },
      guardrails: {
        moderation_enabled: formState.moderationEnabled,
        blocked_categories: listFromCsv(formState.blockedCategories),
        regex_denylist: listFromCsv(formState.regexDenylist),
        escalation_message: formState.escalationMessage || undefined,
      },
      observability: {
        emit_traces: formState.emitTraces,
        capture_prompts: formState.capturePrompts,
        audit_fields: listFromCsv(formState.auditFields),
      },
    };

    const payload: CreateAgentDefinitionPayload | UpdateAgentDefinitionPayload = {
      name: formState.name.trim(),
      description: formState.description || undefined,
      llmConnectionId: formState.llmConnectionId,
      definition: payloadDefinition,
      isActive: formState.isActive,
    };

    setPending(true);
    try {
      if (mode === 'edit' && agentId) {
        await updateAgentDefinition(scopeOrganizationId, agentId, payload as UpdateAgentDefinitionPayload);
        toast({ title: 'Agent updated', description: 'Your agent definition has been saved.' });
      } else {
        await createAgentDefinition(scopeOrganizationId, payload as CreateAgentDefinitionPayload);
        toast({ title: 'Agent created', description: 'Your federated agent is ready to use.' });
      }
      queryClient.invalidateQueries({ queryKey: ['agent-definitions', scopeOrganizationId] });
      onComplete?.();
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'Unable to save agent right now.';
      toast({ title: 'Save failed', description: message, variant: 'destructive' });
    } finally {
      setPending(false);
    }
  };

  const selectedSqlAssetNames = (tool: ToolState): string[] => {
    const ids = tool.analyticalRoute === 'dataset' ? tool.datasetIds : tool.semanticModelIds;
    return tool.analyticalRoute === 'dataset'
      ? ids.map((id) => datasetLookup[id]?.name ?? id)
      : ids.map((id) => semanticModelLookup[id]?.name ?? id);
  };

  const renderSqlToolCard = (tool: ToolState, index: number): JSX.Element => {
    const selectedNames = selectedSqlAssetNames(tool);
    const availableCount = tool.analyticalRoute === 'dataset' ? datasetOptions.length : semanticModelOptions.length;
    const isLoading = tool.analyticalRoute === 'dataset' ? datasetsQuery.isLoading : semanticModelsQuery.isLoading;
    const isError = tool.analyticalRoute === 'dataset' ? datasetsQuery.isError : semanticModelsQuery.isError;

    return (
      <div key={index} className="surface-panel overflow-hidden rounded-[28px] p-5 shadow-soft" style={TOOL_TONES[tool.toolType]}>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{TOOL_LABELS[tool.toolType]}</Badge>
              <Badge variant="secondary">Federated execution</Badge>
              <Badge variant="secondary">{tool.analyticalRoute === 'dataset' ? 'Dataset path' : 'Governed path'}</Badge>
            </div>
            <div>
              <p className="text-lg font-semibold text-[color:var(--text-primary)]">Analyst route {index + 1}</p>
              <p className="text-sm text-[color:var(--text-secondary)]">
                {tool.analyticalRoute === 'dataset'
                  ? 'Query datasets directly. Connectors resolve underneath the dataset abstraction.'
                  : 'Use a semantic model as a governed layer over datasets. Execution still flows through federation.'}
              </p>
            </div>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={() => removeTool(index)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={tool.name} onChange={(event) => updateTool(index, { name: event.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                rows={4}
                value={tool.description}
                onChange={(event) => updateTool(index, { description: event.target.value })}
              />
            </div>
            <div className="surface-card rounded-3xl p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[color:var(--text-primary)]">Current selection</p>
                  <p className="text-xs text-[color:var(--text-muted)]">
                    {selectedNames.length
                      ? `${selectedNames.length} analytical asset${selectedNames.length === 1 ? '' : 's'} selected`
                      : 'No analytical assets selected yet.'}
                  </p>
                </div>
                <Badge variant="secondary">{availableCount} in scope</Badge>
              </div>
              {selectedNames.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedNames.map((name) => (
                    <Badge key={name} variant="secondary">
                      {name}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="surface-card rounded-3xl p-4">
            <Tabs
              defaultValue={tool.analyticalRoute}
              value={tool.analyticalRoute}
              onValueChange={(value) => setSqlRoute(index, value as AnalyticalRoute)}
              className="w-full"
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-sm font-semibold text-[color:var(--text-primary)]">Analytical path</p>
                  <p className="text-xs text-[color:var(--text-muted)]">
                    Datasets are the default route. Semantic models are optional governed overlays.
                  </p>
                </div>
                <TabsList className="w-full lg:w-auto">
                  <TabsTrigger value="dataset">Datasets first</TabsTrigger>
                  <TabsTrigger value="semantic_model">Semantic model</TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="dataset">
                {isLoading ? (
                  <p className="text-sm text-[color:var(--text-muted)]">Loading datasets...</p>
                ) : isError ? (
                  <p className="text-sm text-rose-500">Unable to load datasets right now.</p>
                ) : datasetOptions.length === 0 ? (
                  <div className="rounded-3xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/60 p-5 text-sm text-[color:var(--text-muted)]">
                    Create or publish datasets before attaching an analyst route.
                  </div>
                ) : (
                  <div className="grid max-h-80 gap-3 overflow-auto pr-1">
                    {datasetOptions.map((dataset) => {
                      const selected = tool.datasetIds.includes(dataset.id);
                      return (
                        <label
                          key={dataset.id}
                          className={cn(
                            'block cursor-pointer rounded-3xl border p-4 transition',
                            selected
                              ? 'border-[color:var(--accent)] bg-[color:var(--chip-bg)]'
                              : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] hover:bg-[color:var(--panel-alt)]',
                          )}
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => toggleSqlAsset(index, 'dataset', dataset.id)}
                              className="mt-1 h-4 w-4 rounded border-[color:var(--panel-border)]"
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-semibold text-[color:var(--text-primary)]">{dataset.name}</p>
                                <Badge variant="secondary">{dataset.sqlAlias}</Badge>
                                <Badge variant="secondary">{dataset.datasetType}</Badge>
                              </div>
                              <p className="mt-1 text-xs text-[color:var(--text-muted)]">
                                {dataset.sourceKind} / {dataset.storageKind} / {dataset.columns.length} columns
                              </p>
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="semantic_model">
                {isLoading ? (
                  <p className="text-sm text-[color:var(--text-muted)]">Loading semantic models...</p>
                ) : isError ? (
                  <p className="text-sm text-rose-500">Unable to load semantic models right now.</p>
                ) : semanticModelOptions.length === 0 ? (
                  <div className="rounded-3xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/60 p-5 text-sm text-[color:var(--text-muted)]">
                    Create a dataset-backed semantic model before using the governed route.
                  </div>
                ) : (
                  <div className="grid max-h-80 gap-3 overflow-auto pr-1">
                    {semanticModelOptions.map((model) => {
                      const selected = tool.semanticModelIds.includes(model.id);
                      return (
                        <label
                          key={model.id}
                          className={cn(
                            'block cursor-pointer rounded-3xl border p-4 transition',
                            selected
                              ? 'border-[color:var(--accent)] bg-[color:var(--chip-bg)]'
                              : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] hover:bg-[color:var(--panel-alt)]',
                          )}
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => toggleSqlAsset(index, 'semantic_model', model.id)}
                              className="mt-1 h-4 w-4 rounded border-[color:var(--panel-border)]"
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-semibold text-[color:var(--text-primary)]">{model.name}</p>
                                <Badge variant="secondary">Semantic model</Badge>
                              </div>
                              <p className="mt-1 text-xs text-[color:var(--text-muted)]">
                                {model.description || 'No description provided.'}
                              </p>
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    );
  };

  const renderUtilityToolCard = (tool: ToolState, index: number): JSX.Element => {
    const selectedDefinition = documentDefinitionLookup[readConfigField(tool.config, 'definition_id')];
    return (
      <div key={index} className="surface-panel overflow-hidden rounded-[28px] p-5 shadow-soft" style={TOOL_TONES[tool.toolType]}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{TOOL_LABELS[tool.toolType]}</Badge>
              {tool.toolType === ToolType.web ? <Badge variant="secondary">Live sources</Badge> : <Badge variant="secondary">Internal knowledge</Badge>}
            </div>
            <p className="mt-2 text-lg font-semibold text-[color:var(--text-primary)]">
              {tool.toolType === ToolType.web ? 'Web research tool' : 'Document retrieval tool'}
            </p>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={() => removeTool(index)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={tool.name} onChange={(event) => updateTool(index, { name: event.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea rows={4} value={tool.description} onChange={(event) => updateTool(index, { description: event.target.value })} />
            </div>
          </div>
          <div className="surface-card rounded-3xl p-4">
            {tool.toolType === ToolType.web ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-xs">Max results</Label>
                  <Input type="number" value={readConfigField(tool.config, 'max_results')} onChange={(event) => updateToolConfig(index, { max_results: event.target.value ? Number(event.target.value) : '' })} />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Region</Label>
                  <Input value={readConfigField(tool.config, 'region')} onChange={(event) => updateToolConfig(index, { region: event.target.value })} />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label className="text-xs">Safe search</Label>
                  <Select value={readConfigField(tool.config, 'safe_search')} onChange={(event) => updateToolConfig(index, { safe_search: event.target.value })}>
                    <option value="">Default</option>
                    <option value="off">Off</option>
                    <option value="moderate">Moderate</option>
                    <option value="strict">Strict</option>
                  </Select>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  <Label>Retriever definition</Label>
                  <Select
                    value={readConfigField(tool.config, 'definition_id')}
                    onChange={(event) => {
                      const definition = documentDefinitionLookup[event.target.value];
                      updateToolConfig(index, { definition_id: event.target.value, definition_name: definition?.name ?? '' });
                    }}
                  >
                    <option value="">Select a retriever definition</option>
                    {documentDefinitionOptions.map((definition) => (
                      <option key={definition.id} value={definition.id}>
                        {definition.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <p className="text-xs text-[color:var(--text-muted)]">
                  {selectedDefinition?.description || 'Attach a retriever definition so this tool can ground answers in internal sources.'}
                </p>
                <div className="space-y-2">
                  <Label>Advanced config (JSON)</Label>
                  <Textarea rows={5} value={tool.config} onChange={(event) => updateTool(index, { config: event.target.value })} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 text-[color:var(--text-secondary)]">
      <section className="surface-panel relative overflow-hidden rounded-[32px] p-6 shadow-soft" style={HERO_SECTION_STYLE}>
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[color:var(--text-muted)]">Agent builder</p>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight text-[color:var(--text-primary)]">
                {mode === 'edit' ? 'Refine analytical agent' : 'Design a federated analytical agent'}
              </h1>
              <p className="max-w-2xl text-sm leading-6 text-[color:var(--text-secondary)] md:text-base">
                Configure how the agent reasons over datasets, when it uses semantic models as a governed layer, and
                how it executes through Langbridge&apos;s federated query path.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{scopeLabel}</Badge>
              <Badge variant="secondary">{datasetOptions.length} datasets ready</Badge>
              <Badge variant="secondary">{semanticModelOptions.length} semantic models ready</Badge>
              <Badge variant="secondary">{tools.filter((tool) => tool.toolType === ToolType.sql).length} analyst routes</Badge>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="secondary">{formState.isActive ? 'Active' : 'Inactive'}</Badge>
            <label className="surface-card inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm text-[color:var(--text-primary)] shadow-sm">
              <input
                type="checkbox"
                checked={formState.isActive}
                onChange={(event) => setFormState((prev) => ({ ...prev, isActive: event.target.checked }))}
                className="h-4 w-4 rounded border-[color:var(--panel-border)]"
              />
              Active
            </label>
            {mode === 'edit' ? (
              <Dialog>
                <DialogTrigger>
                  <Button type="button" variant="outline" disabled={pending} className="gap-2">
                    <Trash2 className="h-4 w-4" />
                    <span>Delete agent</span>
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Delete agent definition</DialogTitle>
                    <DialogDescription>This action cannot be undone.</DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <DialogClose>
                      <Button type="button" variant="ghost">Cancel</Button>
                    </DialogClose>
                    <DialogClose>
                      <Button type="button" variant="outline" disabled={pending} onClick={handleDelete}>Delete</Button>
                    </DialogClose>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            ) : null}
          </div>
        </div>

        <div className="mt-6 grid gap-3 lg:grid-cols-3">
          <ArchitectureLane
            icon={<Database className="h-5 w-5" />}
            title="Datasets are the primary asset"
            description="Attach datasets directly to the analyst route. This is now the default structured analysis path."
            stat={`${datasetOptions.length} ready`}
          />
          <ArchitectureLane
            icon={<Network className="h-5 w-5" />}
            title="Execution is federated by default"
            description="Dataset resolution happens before execution and analytical questions route into the federated query runtime."
            stat="Federated"
          />
          <ArchitectureLane
            icon={<Layers3 className="h-5 w-5" />}
            title="Semantic models are optional governance"
            description="Use semantic models when the agent needs governed business vocabulary or curated metrics over datasets."
            stat={`${semanticModelOptions.length} ready`}
          />
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
        <div className="space-y-6">
          <section className="surface-panel rounded-[28px] p-6 shadow-soft">
            <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
              <div className="space-y-4">
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-[color:var(--text-primary)]">Identity</p>
                  <p className="text-xs text-[color:var(--text-muted)]">Name the agent and bind it to an LLM connection.</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="name">Agent name</Label>
                  <Input id="name" value={formState.name} onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))} placeholder="Revenue federation analyst" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea id="description" rows={4} value={formState.description} onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))} placeholder="What analytical work should this agent own?" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="llm-connection">LLM connection</Label>
                  <Select id="llm-connection" value={formState.llmConnectionId} onChange={(event) => setFormState((prev) => ({ ...prev, llmConnectionId: event.target.value }))}>
                    <option value="" disabled>{connectionsQuery.isLoading ? 'Loading...' : 'Select a connection'}</option>
                    {llmOptions.map((connection) => (
                      <option key={connection.id} value={connection.id}>
                        {connection.name} ({connection.provider.toUpperCase()})
                      </option>
                    ))}
                  </Select>
                </div>
              </div>

              <div className="space-y-4">
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-[color:var(--text-primary)]">Prompt contract</p>
                  <p className="text-xs text-[color:var(--text-muted)]">Guide the supervisor toward dataset-first, federated analysis.</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="system-prompt">System prompt</Label>
                  <Textarea id="system-prompt" rows={4} value={formState.systemPrompt} onChange={(event) => setFormState((prev) => ({ ...prev, systemPrompt: event.target.value }))} placeholder="Route analytical questions to the best dataset-backed context." />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="user-instructions">User instructions</Label>
                  <Textarea id="user-instructions" rows={3} value={formState.userInstructions} onChange={(event) => setFormState((prev) => ({ ...prev, userInstructions: event.target.value }))} placeholder="Prefer datasets first. Use semantic models when governed definitions matter." />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="style-guidance">Style guidance</Label>
                  <Input id="style-guidance" value={formState.styleGuidance} onChange={(event) => setFormState((prev) => ({ ...prev, styleGuidance: event.target.value }))} placeholder="Direct, concise, evidence-first" />
                </div>
              </div>
            </div>
          </section>

          <section className="surface-panel rounded-[28px] p-6 shadow-soft">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Analytical routes & tools</p>
                <p className="text-xs leading-5 text-[color:var(--text-muted)]">
                  Build around analytical assets. The analyst route is dataset-first. Semantic models remain optional.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="secondary" size="sm" className="gap-2" onClick={() => addTool(ToolType.sql)}>
                  <Database className="h-4 w-4" />
                  Add analyst route
                </Button>
                <Button type="button" variant="secondary" size="sm" className="gap-2" onClick={() => addTool(ToolType.web)}>
                  <Globe className="h-4 w-4" />
                  Add web research
                </Button>
                <Button type="button" variant="secondary" size="sm" className="gap-2" onClick={() => addTool(ToolType.doc)}>
                  <FileText className="h-4 w-4" />
                  Add document retrieval
                </Button>
              </div>
            </div>

            <div className="mt-5 space-y-4">
              {tools.length === 0 ? (
                <div className="rounded-[28px] border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/50 p-8 text-center">
                  <p className="text-base font-semibold text-[color:var(--text-primary)]">No analytical routes yet</p>
                  <p className="mt-2 text-sm text-[color:var(--text-muted)]">
                    Start with an analyst route and attach datasets. Add semantic models only when the agent needs a
                    governed vocabulary or metric layer.
                  </p>
                </div>
              ) : null}
              {tools.map((tool, index) => (tool.toolType === ToolType.sql ? renderSqlToolCard(tool, index) : renderUtilityToolCard(tool, index)))}
            </div>
          </section>

          <section className="surface-panel rounded-[28px] p-6 shadow-soft">
            <div className="space-y-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Guardrails</p>
                <p className="text-xs text-[color:var(--text-muted)]">Protect downstream responses without changing the analytical routing contract.</p>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-3">
                  <Label className="flex items-center gap-2">
                    <input type="checkbox" checked={formState.moderationEnabled} onChange={(event) => setFormState((prev) => ({ ...prev, moderationEnabled: event.target.checked }))} className="h-4 w-4 rounded border-[color:var(--panel-border)]" />
                    Enable moderation
                  </Label>
                  <div className="space-y-2">
                    <Label>Blocked categories</Label>
                    <Input value={formState.blockedCategories} onChange={(event) => setFormState((prev) => ({ ...prev, blockedCategories: event.target.value }))} placeholder="violence, hate" />
                  </div>
                  <div className="space-y-2">
                    <Label>Regex denylist</Label>
                    <Input value={formState.regexDenylist} onChange={(event) => setFormState((prev) => ({ ...prev, regexDenylist: event.target.value }))} placeholder="secret|password" />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Escalation message</Label>
                  <Textarea rows={6} value={formState.escalationMessage} onChange={(event) => setFormState((prev) => ({ ...prev, escalationMessage: event.target.value }))} placeholder="Content blocked by policy." />
                </div>
              </div>
            </div>
          </section>
        </div>
        <div className="space-y-6">
          <section className="surface-panel rounded-[28px] p-6 shadow-soft">
            <div className="space-y-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Runtime & scope</p>
                <p className="text-xs text-[color:var(--text-muted)]">Control planning behavior and answer style once the asset path is selected.</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/60 p-4">
                  <div className="flex items-center gap-3">
                    <Sparkles className="h-5 w-5 text-[color:var(--accent)]" />
                    <div>
                      <p className="text-sm font-semibold text-[color:var(--text-primary)]">Response mode</p>
                      <p className="text-xs text-[color:var(--text-muted)]">Final answer style.</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <Select value={formState.responseMode} onChange={(event) => setFormState((prev) => ({ ...prev, responseMode: event.target.value as FormState['responseMode'] }))}>
                      {responseModes.map((modeOption) => (
                        <option key={modeOption} value={modeOption}>
                          {responseModeLabels[modeOption]}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>
                <div className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/60 p-4">
                  <div className="flex items-center gap-3">
                    <Bot className="h-5 w-5 text-[color:var(--accent)]" />
                    <div>
                      <p className="text-sm font-semibold text-[color:var(--text-primary)]">Execution mode</p>
                      <p className="text-xs text-[color:var(--text-muted)]">Single response or iterative planning.</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <Select value={formState.executionMode} onChange={(event) => setFormState((prev) => ({ ...prev, executionMode: event.target.value as FormState['executionMode'] }))}>
                      {executionModes.map((modeOption) => (
                        <option key={modeOption} value={modeOption}>
                          {modeOption.replace('_', ' ')}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="max-iterations">Max iterations</Label>
                  <Input id="max-iterations" type="number" value={formState.maxIterations} onChange={(event) => setFormState((prev) => ({ ...prev, maxIterations: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-steps">Max steps / iteration</Label>
                  <Input id="max-steps" type="number" value={formState.maxStepsPerIteration} onChange={(event) => setFormState((prev) => ({ ...prev, maxStepsPerIteration: event.target.value }))} />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label className="flex items-center gap-2">
                    <input type="checkbox" checked={formState.allowParallelTools} onChange={(event) => setFormState((prev) => ({ ...prev, allowParallelTools: event.target.checked }))} className="h-4 w-4 rounded border-[color:var(--panel-border)]" />
                    Allow parallel tools
                  </Label>
                </div>
              </div>

              <div className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/60 p-4">
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Feature flags</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Label className="flex items-center gap-2">
                    <input type="checkbox" checked={formState.biCopilotEnabled} onChange={(event) => setFormState((prev) => ({ ...prev, biCopilotEnabled: event.target.checked }))} className="h-4 w-4 rounded border-[color:var(--panel-border)]" />
                    BI copilot
                  </Label>
                  <Label className="flex items-center gap-2">
                    <input type="checkbox" checked={formState.deepResearchEnabled} onChange={(event) => setFormState((prev) => ({ ...prev, deepResearchEnabled: event.target.checked }))} className="h-4 w-4 rounded border-[color:var(--panel-border)]" />
                    Deep research
                  </Label>
                  <Label className="flex items-center gap-2">
                    <input type="checkbox" checked={formState.visualizationEnabled} onChange={(event) => setFormState((prev) => ({ ...prev, visualizationEnabled: event.target.checked }))} className="h-4 w-4 rounded border-[color:var(--panel-border)]" />
                    Visualization
                  </Label>
                  <Label className="flex items-center gap-2">
                    <input type="checkbox" checked={formState.mcpEnabled} onChange={(event) => setFormState((prev) => ({ ...prev, mcpEnabled: event.target.checked }))} className="h-4 w-4 rounded border-[color:var(--panel-border)]" />
                    MCP
                  </Label>
                </div>
              </div>
            </div>
          </section>

          <section className="surface-panel rounded-[28px] p-6 shadow-soft">
            <div className="space-y-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Memory & access</p>
                <p className="text-xs text-[color:var(--text-muted)]">Connector policy is now an advanced constraint beneath the dataset abstraction.</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="memory-strategy">Strategy</Label>
                  <Select id="memory-strategy" value={formState.memoryStrategy} onChange={(event) => setFormState((prev) => ({ ...prev, memoryStrategy: event.target.value as FormState['memoryStrategy'] }))}>
                    {memoryStrategies.map((strategy) => (
                      <option key={strategy} value={strategy}>
                        {strategy.replace('_', ' ')}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ttl-seconds">TTL (seconds)</Label>
                  <Input id="ttl-seconds" type="number" value={formState.ttlSeconds} onChange={(event) => setFormState((prev) => ({ ...prev, ttlSeconds: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="vector-index">Vector index</Label>
                  <Input id="vector-index" value={formState.vectorIndex} onChange={(event) => setFormState((prev) => ({ ...prev, vectorIndex: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="database-table">DB table</Label>
                  <Input id="database-table" value={formState.databaseTable} onChange={(event) => setFormState((prev) => ({ ...prev, databaseTable: event.target.value }))} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Allowed connectors</Label>
                <Input value={formState.allowedConnectors} onChange={(event) => setFormState((prev) => ({ ...prev, allowedConnectors: event.target.value }))} placeholder="connector-id-1, connector-id-2" />
              </div>
              <div className="space-y-2">
                <Label>Denied connectors</Label>
                <Input value={formState.deniedConnectors} onChange={(event) => setFormState((prev) => ({ ...prev, deniedConnectors: event.target.value }))} placeholder="connector-id-3" />
              </div>
              <div className="space-y-2">
                <Label>Row-level filter</Label>
                <Input value={formState.rowLevelFilter} onChange={(event) => setFormState((prev) => ({ ...prev, rowLevelFilter: event.target.value }))} placeholder="department = 'finance'" />
              </div>
              <div className="space-y-2">
                <Label>PII handling</Label>
                <Textarea rows={3} value={formState.piiHandling} onChange={(event) => setFormState((prev) => ({ ...prev, piiHandling: event.target.value }))} placeholder="Mask emails in responses" />
              </div>
            </div>
          </section>

          <section className="surface-panel rounded-[28px] p-6 shadow-soft">
            <div className="space-y-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Output & observability</p>
                <p className="text-xs text-[color:var(--text-muted)]">Shape outputs, traces, and audit metadata.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="output-format">Format</Label>
                <Select id="output-format" value={formState.outputFormat} onChange={(event) => setFormState((prev) => ({ ...prev, outputFormat: event.target.value as FormState['outputFormat'] }))}>
                  {outputFormats.map((format) => (
                    <option key={format} value={format}>
                      {format.toUpperCase()}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label>JSON schema</Label>
                <Textarea rows={4} value={formState.jsonSchema} onChange={(event) => setFormState((prev) => ({ ...prev, jsonSchema: event.target.value }))} placeholder='{ "type": "object", "properties": { ... } }' />
              </div>
              <div className="space-y-2">
                <Label>Markdown template</Label>
                <Textarea rows={3} value={formState.markdownTemplate} onChange={(event) => setFormState((prev) => ({ ...prev, markdownTemplate: event.target.value }))} placeholder="## Summary" />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Label className="flex items-center gap-2">
                  <input type="checkbox" checked={formState.emitTraces} onChange={(event) => setFormState((prev) => ({ ...prev, emitTraces: event.target.checked }))} className="h-4 w-4 rounded border-[color:var(--panel-border)]" />
                  Emit traces
                </Label>
                <Label className="flex items-center gap-2">
                  <input type="checkbox" checked={formState.capturePrompts} onChange={(event) => setFormState((prev) => ({ ...prev, capturePrompts: event.target.checked }))} className="h-4 w-4 rounded border-[color:var(--panel-border)]" />
                  Capture prompts
                </Label>
              </div>
              <div className="space-y-2">
                <Label>Audit fields</Label>
                <Input value={formState.auditFields} onChange={(event) => setFormState((prev) => ({ ...prev, auditFields: event.target.value }))} placeholder="user_id, project_id" />
              </div>
              {agentId ? (
                <p className="text-xs text-[color:var(--text-muted)]">Linked connection: {connectionLookup[formState.llmConnectionId] ?? formState.llmConnectionId}</p>
              ) : null}
            </div>
          </section>
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <Button type="submit" disabled={pending || connectionsQuery.isLoading} className="gap-2">
          {pending ? 'Saving...' : mode === 'edit' ? 'Save changes' : 'Create agent'}
        </Button>
      </div>
    </form>
  );
}
