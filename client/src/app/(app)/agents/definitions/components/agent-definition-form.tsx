'use client';

import { JSX, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Plus, Trash2 } from 'lucide-react';
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
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import {
  createAgentDefinition,
  fetchAgentDefinition,
  fetchLLMConnections,
  getAvailableFileRetriverDefinitions,
  getAvailableSemanticModels,
  getAvailableSemanticSearchDefinitions,
  updateAgentDefinition,
} from '@/orchestration/agents';
import type {
  AgentDefinition,
  CreateAgentDefinitionPayload,
  LLMConnection,
  UpdateAgentDefinitionPayload,
} from '@/orchestration/agents';
import { ApiError } from '@/orchestration/http';

// const memoryStrategies = ['none', 'transient', 'conversation', 'long_term', 'vector', 'database'] as const;
const memoryStrategies = ['database'] as const;
const executionModes = ['single_step', 'iterative'] as const;
const outputFormats = ['text', 'markdown', 'json', 'yaml'] as const;
// const logLevels = ['debug', 'info', 'warning', 'error', 'critical'] as const;

interface ToolState {
  name: string;
  connectorId: string;
  description: string;
  config: string;
}

interface FormState {
  name: string;
  description: string;
  llmConnectionId: string;
  isActive: boolean;
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
  // logLevel: (typeof logLevels)[number];
  emitTraces: boolean;
  capturePrompts: boolean;
  auditFields: string;
}

interface ToolDefinitionOption {
  id: string;
  name: string;
  description: string;
}

enum ToolType {
  sql_analyst = 'sql_analyst',
  web_search = 'web_search',
  deep_research = 'deep_research',
  file_retriever = 'file_retriever',
  semantic_searcher = 'semantic_searcher',
}

const ToolTypeLabels: Record<ToolType, string> = {
  [ToolType.sql_analyst]: 'SQL Analyst',
  [ToolType.web_search]: 'Web Search',
  [ToolType.deep_research]: 'Deep Research',
  [ToolType.file_retriever]: 'File Retriever',
  [ToolType.semantic_searcher]: 'Semantic Searcher',
};

const ToolTypeOptions: ToolType[] = [
  ToolType.sql_analyst,
  ToolType.web_search,
  ToolType.deep_research,
  ToolType.file_retriever,
  ToolType.semantic_searcher,
];

const ToolDefinitionLabels: Record<ToolType, string> = {
  [ToolType.sql_analyst]: 'Semantic model',
  [ToolType.web_search]: 'Web search definition',
  [ToolType.deep_research]: 'Research definition',
  [ToolType.file_retriever]: 'File retriever definition',
  [ToolType.semantic_searcher]: 'Semantic search definition',
};

const TOOL_TYPES_WITH_DEFINITIONS = new Set<ToolType>([
  ToolType.sql_analyst,
  ToolType.file_retriever,
  ToolType.semantic_searcher,
]);

const TOOL_DEFAULT_DESCRIPTIONS: Record<ToolType, string> = {
  [ToolType.sql_analyst]: 'Query structured data through semantic models.',
  [ToolType.web_search]: 'Search the public web for sources and summaries.',
  [ToolType.deep_research]: 'Synthesize insights from documents and sources.',
  [ToolType.file_retriever]: 'Retrieve files from configured sources.',
  [ToolType.semantic_searcher]: 'Run semantic retrieval over embeddings.',
};

const TOOL_DEFAULT_CONFIG: Record<ToolType, Record<string, unknown>> = {
  [ToolType.sql_analyst]: {},
  [ToolType.web_search]: { max_results: 6, safe_search: 'moderate' },
  [ToolType.deep_research]: {},
  [ToolType.file_retriever]: {},
  [ToolType.semantic_searcher]: {},
};

const ALL_SEMANTIC_MODELS_OPTION = '__all__';

const WEB_SEARCH_TOOL_NAMES = new Set(['web_search', 'web_searcher', 'web_search_agent']);

function normalizeToolName(value: string): string {
  return value.trim().toLowerCase();
}

function isWebSearchTool(value: string): boolean {
  return WEB_SEARCH_TOOL_NAMES.has(normalizeToolName(value));
}

function defaultFormState(): FormState {
  return {
    name: '',
    description: '',
    llmConnectionId: '',
    isActive: true,
    systemPrompt: '',
    userInstructions: '',
    styleGuidance: '',
    memoryStrategy: 'database',
    ttlSeconds: '',
    vectorIndex: '',
    databaseTable: '',
    tools: [
      {
        name: '',
        connectorId: '',
        description: '',
        config: '{}',
      },
    ],
    allowedConnectors: '',
    deniedConnectors: '',
    piiHandling: '',
    rowLevelFilter: '',
    executionMode: 'single_step',
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
    // logLevel: 'info',
    emitTraces: true,
    capturePrompts: true,
    auditFields: '',
  };
}

function listFromCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseJsonSafe(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
}

function stringifyConfig(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

function readConfigField(config: string, key: string): string {
  const parsed = parseJsonSafe(config);
  if (!parsed || typeof parsed !== 'object') {
    return '';
  }
  const value = (parsed as Record<string, unknown>)[key];
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return '';
}

function hydrateFromDefinition(definition: unknown, base: FormState): FormState {
  if (!definition || typeof definition !== 'object') {
    return base;
  }

  const payload = definition as Record<string, any>;
  const prompt = (payload.prompt as Record<string, any>) ?? {};
  const memory = (payload.memory as Record<string, any>) ?? {};
  const tools = Array.isArray(payload.tools) ? payload.tools : [];
  const accessPolicy = (payload.access_policy as Record<string, any>) ?? {};
  const execution = (payload.execution as Record<string, any>) ?? {};
  const output = (payload.output as Record<string, any>) ?? {};
  const guardrails = (payload.guardrails as Record<string, any>) ?? {};
  const observability = (payload.observability as Record<string, any>) ?? {};

  return {
    ...base,
    systemPrompt: prompt.system_prompt ?? '',
    userInstructions: prompt.user_instructions ?? '',
    styleGuidance: prompt.style_guidance ?? '',
    memoryStrategy: memory.strategy ?? base.memoryStrategy,
    ttlSeconds: memory.ttl_seconds?.toString() ?? '',
    vectorIndex: memory.vector_index ?? '',
    databaseTable: memory.database_table ?? '',
    tools: tools.length
      ? tools.map((tool: any) => ({
          name: tool.name ?? '',
          connectorId: tool.connector_id ?? '',
          description: tool.description ?? '',
          config: stringifyConfig(tool.config ?? {}),
        }))
      : base.tools,
    allowedConnectors: (accessPolicy.allowed_connectors ?? []).join(', '),
    deniedConnectors: (accessPolicy.denied_connectors ?? []).join(', '),
    piiHandling: accessPolicy.pii_handling ?? '',
    rowLevelFilter: accessPolicy.row_level_filter ?? '',
    executionMode: execution.mode ?? base.executionMode,
    maxIterations: execution.max_iterations?.toString() ?? base.maxIterations,
    maxStepsPerIteration: execution.max_steps_per_iteration?.toString() ?? base.maxStepsPerIteration,
    allowParallelTools: Boolean(execution.allow_parallel_tools ?? base.allowParallelTools),
    outputFormat: output.format ?? base.outputFormat,
    jsonSchema: output.json_schema ? stringifyConfig(output.json_schema) : '',
    markdownTemplate: output.markdown_template ?? '',
    moderationEnabled: guardrails.moderation_enabled ?? base.moderationEnabled,
    blockedCategories: (guardrails.blocked_categories ?? []).join(', '),
    regexDenylist: (guardrails.regex_denylist ?? []).join(', '),
    escalationMessage: guardrails.escalation_message ?? '',
    // logLevel: observability.log_level ?? base.logLevel,
    emitTraces: observability.emit_traces ?? base.emitTraces,
    capturePrompts: observability.capture_prompts ?? base.capturePrompts,
    auditFields: (observability.audit_fields ?? []).join(', '),
  };
}

interface AgentDefinitionFormProps {
  mode: 'create' | 'edit';
  agentId?: string;
  initialAgent?: AgentDefinition | null;
  onComplete?: () => void;
}

export function AgentDefinitionForm({ mode, agentId, initialAgent, onComplete }: AgentDefinitionFormProps): JSX.Element {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { selectedOrganizationId } = useWorkspaceScope();
  const [formState, setFormState] = useState<FormState>(defaultFormState());
  const [pending, setPending] = useState(false);
  const [toolPickerOpen, setToolPickerOpen] = useState(false);
  const [selectedToolType, setSelectedToolType] = useState<ToolType | ''>('');
  const [selectedToolDefinitionId, setSelectedToolDefinitionId] = useState('');

  const connectionsQuery = useQuery<LLMConnection[]>({
    queryKey: ['llm-connections'],
    queryFn: () => fetchLLMConnections(),
  });

  const toolSupportsDefinitions = Boolean(
    selectedToolType && TOOL_TYPES_WITH_DEFINITIONS.has(selectedToolType as ToolType),
  );

  const toolDefinitionsQuery = useQuery<ToolDefinitionOption[]>({
    queryKey: ['agent-tool-definitions', selectedToolType],
    enabled: toolPickerOpen && toolSupportsDefinitions,
    queryFn: async () => {
      switch (selectedToolType) {
        case ToolType.sql_analyst: {
          const models = await getAvailableSemanticModels(selectedOrganizationId ?? '');
          return models.map((model) => ({
            id: model.id,
            name: model.name,
            description: model.description ?? '',
          }));
        }
        case ToolType.file_retriever: {
          const retrievers = await getAvailableFileRetriverDefinitions();
          return retrievers.map((retriever) => ({
            id: retriever.id,
            name: retriever.name,
            description: retriever.description ?? '',
          }));
        }
        case ToolType.semantic_searcher: {
          const searches = await getAvailableSemanticSearchDefinitions();
          return searches.map((search) => ({
            id: search.id,
            name: search.name,
            description: search.description ?? '',
          }));
        }
        default:
          return [];
      }
    },
  });

  useQuery<AgentDefinition>({
    queryKey: ['agent-definition', agentId],
    enabled: mode === 'edit' && Boolean(agentId) && !initialAgent,
    queryFn: () => fetchAgentDefinition(agentId ?? ''),
    onSuccess: (agent: AgentDefinition) => {
      const base = defaultFormState();
      setFormState({
        ...hydrateFromDefinition(agent.definition, base),
        name: agent.name,
        description: agent.description ?? '',
        llmConnectionId: agent.llmConnectionId,
        isActive: agent.isActive,
      });
    },
  });

  useEffect(() => {
    if (initialAgent) {
      const base = defaultFormState();
      setFormState({
        ...hydrateFromDefinition(initialAgent.definition, base),
        name: initialAgent.name,
        description: initialAgent.description ?? '',
        llmConnectionId: initialAgent.llmConnectionId,
        isActive: initialAgent.isActive,
      });
    }
  }, [initialAgent]);

  useEffect(() => {
    const connections = connectionsQuery.data ?? [];
    if (!formState.llmConnectionId && connections.length > 0) {
      setFormState((prev) => ({ ...prev, llmConnectionId: connections[0].id }));
    }
  }, [connectionsQuery.data, formState.llmConnectionId]);

  useEffect(() => {
    if (!toolPickerOpen) {
      setSelectedToolType('');
      setSelectedToolDefinitionId('');
    }
  }, [toolPickerOpen]);

  useEffect(() => {
    setSelectedToolDefinitionId('');
  }, [selectedToolType]);

  useEffect(() => {
    if (!toolPickerOpen) {
      return;
    }
    if (selectedToolType !== ToolType.sql_analyst) {
      return;
    }
    if (!toolDefinitionsQuery.data || toolDefinitionsQuery.data.length === 0) {
      return;
    }
    if (!selectedToolDefinitionId) {
      setSelectedToolDefinitionId(ALL_SEMANTIC_MODELS_OPTION);
    }
  }, [selectedToolDefinitionId, selectedToolType, toolDefinitionsQuery.data, toolPickerOpen]);

  const tools = formState.tools;
  const toolDefinitionOptions = toolDefinitionsQuery.data ?? [];
  const selectedToolDefinition = toolDefinitionOptions.find((option) => option.id === selectedToolDefinitionId);
  const toolDefinitionLabel = selectedToolType ? ToolDefinitionLabels[selectedToolType] : 'Definition';
  const canAddTool = Boolean(selectedToolType) && !toolDefinitionsQuery.isLoading;

  const connectionLookup = useMemo(() => {
    return Object.fromEntries((connectionsQuery.data ?? []).map((conn) => [conn.id, conn.name]));
  }, [connectionsQuery.data]);

  const handleToolChange = (index: number, field: keyof ToolState, value: string) => {
    setFormState((prev) => {
      const nextTools = prev.tools.slice();
      nextTools[index] = { ...nextTools[index], [field]: value } as ToolState;
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
        if (value === '' || value === undefined || value === null) {
          delete nextConfig[key];
        } else {
          nextConfig[key] = value;
        }
      });

      nextTools[index] = {
        ...nextTools[index],
        config: stringifyConfig(nextConfig) || '{}',
      };
      return { ...prev, tools: nextTools };
    });
  };

  const handleAddTool = () => {
    if (!selectedToolType) {
      return;
    }

    const configPayload: Record<string, unknown> = {
      ...TOOL_DEFAULT_CONFIG[selectedToolType],
    };
    const shouldAttachDefinition =
      Boolean(selectedToolDefinition) && selectedToolDefinitionId !== ALL_SEMANTIC_MODELS_OPTION;
    if (shouldAttachDefinition && selectedToolDefinition) {
      configPayload.definition_id = selectedToolDefinition.id;
      configPayload.definition_name = selectedToolDefinition.name;
    }

    setFormState((prev) => ({
      ...prev,
      tools: [
        ...prev.tools,
        {
          name: selectedToolType,
          connectorId: '',
          description: selectedToolDefinition?.description ?? TOOL_DEFAULT_DESCRIPTIONS[selectedToolType],
          config: stringifyConfig(configPayload) || '{}',
        },
      ],
    }));
    setToolPickerOpen(false);
  };

  const removeTool = (index: number) => {
    setFormState((prev) => ({
      ...prev,
      tools: prev.tools.filter((_, i) => i !== index),
    }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!formState.name.trim()) {
      toast({ title: 'Name is required', variant: 'destructive' });
      return;
    }
    if (!formState.llmConnectionId) {
      toast({ title: 'Select a connection', description: 'Choose an LLM connection for this agent.' });
      return;
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
      tools: tools
        .filter((tool) => tool.name.trim())
        .map((tool) => ({
          name: tool.name.trim(),
          connector_id: tool.connectorId || undefined,
          description: tool.description || undefined,
          config: parseJsonSafe(tool.config),
        })),
      access_policy: {
        allowed_connectors: listFromCsv(formState.allowedConnectors),
        denied_connectors: listFromCsv(formState.deniedConnectors),
        pii_handling: formState.piiHandling || undefined,
        row_level_filter: formState.rowLevelFilter || undefined,
      },
      execution: {
        mode: formState.executionMode,
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
        // log_level: formState.logLevel,
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
        await updateAgentDefinition(agentId, payload as UpdateAgentDefinitionPayload);
        toast({ title: 'Agent updated', description: 'Your agent definition has been saved.' });
        queryClient.invalidateQueries({ queryKey: ['agent-definitions'] });
      } else {
        await createAgentDefinition(payload as CreateAgentDefinitionPayload);
        queryClient.invalidateQueries({ queryKey: ['agent-definitions'] });
        toast({ title: 'Agent created', description: 'Your agent is ready to use.' });
      }
      if (onComplete) {
        onComplete();
      }
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

  const connections = connectionsQuery.data ?? [];
  const llmOptions = connections.filter((conn) =>
    selectedOrganizationId ? conn.organizationId === selectedOrganizationId || !conn.organizationId : true,
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              Agent builder
            </p>
            <h1 className="text-2xl font-semibold text-[color:var(--text-primary)]">
              {mode === 'edit' ? 'Edit agent' : 'Create a new agent'}
            </h1>
            <p className="text-sm text-[color:var(--text-secondary)]">
              Define prompts, memory, tools, and guardrails. We’ll store the definition and wire it to an existing LLM
              connection.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="secondary">{formState.isActive ? 'Active' : 'Inactive'}</Badge>
            <div className="flex items-center gap-2 text-sm text-[color:var(--text-muted)]">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formState.isActive}
                  onChange={(e) => setFormState((prev) => ({ ...prev, isActive: e.target.checked }))}
                  className="h-4 w-4 rounded border-[color:var(--panel-border)]"
                />
                Active
              </label>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Agent name</Label>
              <Input
                id="name"
                placeholder="Revenue analyst"
                value={formState.name}
                onChange={(e) => setFormState((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                rows={3}
                placeholder="What is this agent great at?"
                value={formState.description}
                onChange={(e) => setFormState((prev) => ({ ...prev, description: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="llm-connection">LLM connection</Label>
              <Select
                id="llm-connection"
                value={formState.llmConnectionId}
                onChange={(e) => setFormState((prev) => ({ ...prev, llmConnectionId: e.target.value }))}
              >
                <option value="" disabled>
                  {connectionsQuery.isLoading ? 'Loading...' : 'Select a connection'}
                </option>
                {llmOptions.map((connection) => (
                  <option key={connection.id} value={connection.id}>
                    {connection.name} ({connection.provider.toUpperCase()})
                  </option>
                ))}
              </Select>
              {!llmOptions.length && !connectionsQuery.isLoading ? (
                <p className="text-xs text-[color:var(--text-muted)]">Create an LLM connection first.</p>
              ) : null}
            </div>
          </div>
        </section>

        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Prompt contract</p>
                <p className="text-xs text-[color:var(--text-muted)]">System guidance and style.</p>
              </div>
            </div>
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="system-prompt">System prompt</Label>
                <Textarea
                  id="system-prompt"
                  rows={3}
                  value={formState.systemPrompt}
                  onChange={(e) => setFormState((prev) => ({ ...prev, systemPrompt: e.target.value }))}
                  placeholder="You are a data analyst..."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="user-instructions">User instructions</Label>
                <Textarea
                  id="user-instructions"
                  rows={2}
                  value={formState.userInstructions}
                  onChange={(e) => setFormState((prev) => ({ ...prev, userInstructions: e.target.value }))}
                  placeholder="Interpret questions as business requests..."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="style-guidance">Style guidance</Label>
                <Input
                  id="style-guidance"
                  value={formState.styleGuidance}
                  onChange={(e) => setFormState((prev) => ({ ...prev, styleGuidance: e.target.value }))}
                  placeholder="Concise, factual, bullet-first"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Memory</p>
                <p className="text-xs text-[color:var(--text-muted)]">Pick how context is persisted.</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="memory-strategy">Strategy</Label>
                <Select
                  id="memory-strategy"
                  value={formState.memoryStrategy}
                  onChange={(e) => setFormState((prev) => ({
                    ...prev,
                    memoryStrategy: e.target.value as FormState['memoryStrategy'],
                  }))}
                >
                  {memoryStrategies.map((strategy) => (
                    <option key={strategy} value={strategy}>
                      {strategy.replace('_', ' ')}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="ttl-seconds">TTL (seconds)</Label>
                <Input
                  id="ttl-seconds"
                  type="number"
                  value={formState.ttlSeconds}
                  onChange={(e) => setFormState((prev) => ({ ...prev, ttlSeconds: e.target.value }))}
                  placeholder="300"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="vector-index">Vector index</Label>
                <Input
                  id="vector-index"
                  value={formState.vectorIndex}
                  onChange={(e) => setFormState((prev) => ({ ...prev, vectorIndex: e.target.value }))}
                  placeholder="analytics_vectors"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="database-table">DB table</Label>
                <Input
                  id="database-table"
                  value={formState.databaseTable}
                  onChange={(e) => setFormState((prev) => ({ ...prev, databaseTable: e.target.value }))}
                  placeholder="agent_memory"
                />
              </div>
            </div>
          </div>
        </section>

        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Data access & policy</p>
                <p className="text-xs text-[color:var(--text-muted)]">Constrain connectors and rows.</p>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Allowed connectors</Label>
              <Input
                placeholder="connector-id-1, connector-id-2"
                value={formState.allowedConnectors}
                onChange={(e) => setFormState((prev) => ({ ...prev, allowedConnectors: e.target.value }))}
              />
              <p className="text-xs text-[color:var(--text-muted)]">Comma-separated connector IDs.</p>
            </div>
            <div className="space-y-2">
              <Label>Denied connectors</Label>
              <Input
                placeholder="blocklist-id"
                value={formState.deniedConnectors}
                onChange={(e) => setFormState((prev) => ({ ...prev, deniedConnectors: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Row-level filter</Label>
              <Input
                placeholder="department = 'finance'"
                value={formState.rowLevelFilter}
                onChange={(e) => setFormState((prev) => ({ ...prev, rowLevelFilter: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>PII handling</Label>
              <Textarea
                rows={2}
                placeholder="Mask emails in responses"
                value={formState.piiHandling}
                onChange={(e) => setFormState((prev) => ({ ...prev, piiHandling: e.target.value }))}
              />
            </div>
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Execution</p>
                <p className="text-xs text-[color:var(--text-muted)]">Control planning behavior.</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="execution-mode">Mode</Label>
                <Select
                  id="execution-mode"
                  value={formState.executionMode}
                  onChange={(e) => setFormState((prev) => ({
                    ...prev,
                    executionMode: e.target.value as FormState['executionMode'],
                  }))}
                >
                  {executionModes.map((modeOption) => (
                    <option key={modeOption} value={modeOption}>
                      {modeOption.replace('_', ' ')}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="max-iterations">Max iterations</Label>
                <Input
                  id="max-iterations"
                  type="number"
                  value={formState.maxIterations}
                  onChange={(e) => setFormState((prev) => ({ ...prev, maxIterations: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="max-steps">Max steps / iteration</Label>
                <Input
                  id="max-steps"
                  type="number"
                  value={formState.maxStepsPerIteration}
                  onChange={(e) => setFormState((prev) => ({ ...prev, maxStepsPerIteration: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formState.allowParallelTools}
                    onChange={(e) => setFormState((prev) => ({ ...prev, allowParallelTools: e.target.checked }))}
                    className="h-4 w-4 rounded border-[color:var(--panel-border)]"
                  />
                  Allow parallel tools
                </Label>
              </div>
            </div>
          </div>
        </section>

        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Output & schema</p>
                <p className="text-xs text-[color:var(--text-muted)]">Enforce output format.</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="output-format">Format</Label>
                <Select
                  id="output-format"
                  value={formState.outputFormat}
                  onChange={(e) => setFormState((prev) => ({
                    ...prev,
                    outputFormat: e.target.value as FormState['outputFormat'],
                  }))}
                >
                  {outputFormats.map((format) => (
                    <option key={format} value={format}>
                      {format.toUpperCase()}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>JSON schema</Label>
              <Textarea
                rows={4}
                placeholder='{ "type": "object", "properties": { ... } }'
                value={formState.jsonSchema}
                onChange={(e) => setFormState((prev) => ({ ...prev, jsonSchema: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Markdown template</Label>
              <Textarea
                rows={3}
                placeholder="## Summary\n- bullet"
                value={formState.markdownTemplate}
                onChange={(e) => setFormState((prev) => ({ ...prev, markdownTemplate: e.target.value }))}
              />
            </div>
          </div>
        </section>
      </div>

      <section className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-[color:var(--text-primary)]">Tools & connectors</p>
            <p className="text-xs text-[color:var(--text-muted)]">Map functions or connectors the agent can call.</p>
          </div>
          <Dialog open={toolPickerOpen} onOpenChange={setToolPickerOpen}>
            <DialogTrigger>
              <Button type="button" size="sm" className="gap-2">
                <Plus className="h-4 w-4" /> Add tool
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-xl">
              <DialogHeader>
                <DialogTitle>Add tool</DialogTitle>
                <DialogDescription>
                  Pick a tool type. Built-in tools can be added immediately, while others can be scoped to a definition.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="tool-type">Tool type</Label>
                  <Select
                    id="tool-type"
                    value={selectedToolType}
                    onChange={(event) => setSelectedToolType(event.target.value as ToolType)}
                    placeholder="Choose a tool type"
                  >
                    {ToolTypeOptions.map((toolType) => (
                      <option key={toolType} value={toolType}>
                        {ToolTypeLabels[toolType]}
                      </option>
                    ))}
                  </Select>
                </div>
                {selectedToolType ? (
                  toolSupportsDefinitions ? (
                    <div className="space-y-2">
                      <Label htmlFor="tool-definition">{toolDefinitionLabel}</Label>
                      {toolDefinitionsQuery.isLoading ? (
                        <p className="text-xs text-[color:var(--text-muted)]">Loading available definitions...</p>
                      ) : toolDefinitionsQuery.isError ? (
                        <p className="text-xs text-rose-500">Unable to load definitions right now.</p>
                      ) : toolDefinitionOptions.length ? (
                        <>
                          <Select
                            id="tool-definition"
                            value={selectedToolDefinitionId}
                            onChange={(event) => setSelectedToolDefinitionId(event.target.value)}
                            placeholder={`Select a ${toolDefinitionLabel.toLowerCase()}`}
                          >
                            {selectedToolType === ToolType.sql_analyst ? (
                              <option value={ALL_SEMANTIC_MODELS_OPTION}>All semantic models</option>
                            ) : null}
                            {toolDefinitionOptions.map((option) => (
                              <option key={option.id} value={option.id}>
                                {option.name}
                              </option>
                            ))}
                          </Select>
                          {selectedToolDefinition ? (
                            <p className="text-xs text-[color:var(--text-muted)]">
                              {selectedToolDefinition.description || 'No description provided.'}
                            </p>
                          ) : selectedToolDefinitionId === ALL_SEMANTIC_MODELS_OPTION ? (
                            <p className="text-xs text-[color:var(--text-muted)]">
                              All available semantic models will be available to this agent.
                            </p>
                          ) : null}
                        </>
                      ) : (
                        <p className="text-xs text-[color:var(--text-muted)]">
                          No definitions available yet. You can still add the tool and configure it manually.
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-[color:var(--text-muted)]">
                      This is a built-in tool. You can configure it after adding.
                    </p>
                  )
                ) : null}
              </div>
              <DialogFooter>
                <DialogClose>
                  <Button type="button" variant="ghost">
                    Cancel
                  </Button>
                </DialogClose>
                <Button type="button" onClick={handleAddTool} disabled={!canAddTool}>
                  Add tool
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
        <div className="mt-4 space-y-3">
          {tools.map((tool, index) => (
            <div
              key={index}
              className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Tool {index + 1}</p>
                {tools.length > 1 ? (
                  <Button variant="ghost" size="icon" type="button" onClick={() => removeTool(index)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                ) : null}
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={tool.name}
                    onChange={(e) => handleToolChange(index, 'name', e.target.value)}
                    placeholder="sql-analyst"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Connector ID</Label>
                  <Input
                    value={tool.connectorId}
                    onChange={(e) => handleToolChange(index, 'connectorId', e.target.value)}
                    placeholder="optional connector id"
                  />
                </div>
              </div>
              <div className="mt-3 space-y-2">
                <Label>Description</Label>
                <Input
                  value={tool.description}
                  onChange={(e) => handleToolChange(index, 'description', e.target.value)}
                  placeholder="Short description"
                />
              </div>
              <div className="mt-3 space-y-2">
                <Label>Config (JSON)</Label>
                <Textarea
                  rows={3}
                  value={tool.config}
                  onChange={(e) => handleToolChange(index, 'config', e.target.value)}
                />
              </div>
              {isWebSearchTool(tool.name) ? (
                <div className="mt-4 grid gap-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-xs text-[color:var(--text-muted)] sm:grid-cols-3">
                  <div className="space-y-2">
                    <Label className="text-xs">Max results</Label>
                    <Input
                      type="number"
                      min={1}
                      max={20}
                      value={readConfigField(tool.config, 'max_results')}
                      onChange={(event) => {
                        const rawValue = event.target.value;
                        updateToolConfig(index, {
                          max_results: rawValue ? Number(rawValue) : '',
                        });
                      }}
                      placeholder="6"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Region</Label>
                    <Input
                      value={readConfigField(tool.config, 'region')}
                      onChange={(event) => updateToolConfig(index, { region: event.target.value })}
                      placeholder="us-en"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Safe search</Label>
                    <Select
                      value={readConfigField(tool.config, 'safe_search')}
                      onChange={(event) => updateToolConfig(index, { safe_search: event.target.value })}
                    >
                      <option value="">Default</option>
                      <option value="off">Off</option>
                      <option value="moderate">Moderate</option>
                      <option value="strict">Strict</option>
                    </Select>
                  </div>
                  <p className="sm:col-span-3">
                    These fields map to the web search tool config (`max_results`, `region`, `safe_search`).
                  </p>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Guardrails</p>
                <p className="text-xs text-[color:var(--text-muted)]">Moderation and deny lists.</p>
              </div>
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formState.moderationEnabled}
                  onChange={(e) => setFormState((prev) => ({ ...prev, moderationEnabled: e.target.checked }))}
                  className="h-4 w-4 rounded border-[color:var(--panel-border)]"
                />
                Enable moderation
              </Label>
            </div>
            <div className="space-y-2">
              <Label>Blocked categories</Label>
              <Input
                placeholder="violence, hate"
                value={formState.blockedCategories}
                onChange={(e) => setFormState((prev) => ({ ...prev, blockedCategories: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Regex denylist</Label>
              <Input
                placeholder="secret|password"
                value={formState.regexDenylist}
                onChange={(e) => setFormState((prev) => ({ ...prev, regexDenylist: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Escalation message</Label>
              <Textarea
                rows={2}
                placeholder="Content blocked by policy."
                value={formState.escalationMessage}
                onChange={(e) => setFormState((prev) => ({ ...prev, escalationMessage: e.target.value }))}
              />
            </div>
          </div>
        </section>

        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Observability</p>
                <p className="text-xs text-[color:var(--text-muted)]">Tracing, prompts, and audit fields.</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formState.emitTraces}
                    onChange={(e) => setFormState((prev) => ({ ...prev, emitTraces: e.target.checked }))}
                    className="h-4 w-4 rounded border-[color:var(--panel-border)]"
                  />
                  Emit traces
                </Label>
              </div>
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formState.capturePrompts}
                    onChange={(e) => setFormState((prev) => ({ ...prev, capturePrompts: e.target.checked }))}
                    className="h-4 w-4 rounded border-[color:var(--panel-border)]"
                  />
                  Capture prompts
                </Label>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Audit fields</Label>
              <Input
                placeholder="user_id, project_id"
                value={formState.auditFields}
                onChange={(e) => setFormState((prev) => ({ ...prev, auditFields: e.target.value }))}
              />
            </div>
            {agentId ? (
              <p className="text-xs text-[color:var(--text-muted)]">Linked connection: {connectionLookup[formState.llmConnectionId] ?? formState.llmConnectionId}</p>
            ) : null}
          </div>
        </section>
      </div>

      <div className="flex justify-end gap-3">
        <Button type="submit" disabled={pending || connectionsQuery.isLoading} className="gap-2">
          {pending ? 'Saving...' : mode === 'edit' ? 'Save changes' : 'Create agent'}
        </Button>
      </div>
    </form>
  );
}
