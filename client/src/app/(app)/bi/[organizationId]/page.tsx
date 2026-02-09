'use client';

import { use, useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { fetchAgentDefinitions } from '@/orchestration/agents';
import type { AgentDefinition } from '@/orchestration/agents/types';
import { enqueueDashboardCopilotJob } from '@/orchestration/copilot';
import type { DashboardCopilotJobResponsePayload } from '@/orchestration/copilot/types';
import {
  createDashboard,
  deleteDashboard,
  getDashboardSnapshot,
  listDashboards,
  upsertDashboardSnapshot,
  updateDashboard,
} from '@/orchestration/dashboards';
import type {
  DashboardCreatePayload,
  DashboardRecord,
  DashboardSnapshotRecord,
  DashboardSnapshotUpsertPayload,
  DashboardUpdatePayload,
} from '@/orchestration/dashboards/types';
import { listSemanticModels } from '@/orchestration/semanticModels';
import type { SemanticModelRecord } from '@/orchestration/semanticModels/types';
import { fetchAgentJobState } from '@/orchestration/jobs';
import { enqueueSemanticQuery, fetchSemanticQueryMeta } from '@/orchestration/semanticQuery';
import type {
  SemanticModelPayload,
  SemanticQueryJobResponse,
  SemanticQueryMetaResponse,
  SemanticQueryRequestPayload,
  SemanticQueryResponse,
} from '@/orchestration/semanticQuery/types';

import { BiAiInput } from '../_components/BiAiInput';
import { BiCanvas } from '../_components/BiCanvas';
import { BiConfigPanel } from '../_components/BiConfigPanel';
import { BiGlobalConfigPanel } from '../_components/BiGlobalConfigPanel';
import { BiHeader } from '../_components/BiHeader';
import { BiSidebar } from '../_components/BiSidebar';
import type {
  BiWidget,
  FieldOption,
  FilterDraft,
  PersistedBiWidget,
  TableGroup,
} from '../types';

type BiStudioPageProps = {
  params: Promise<{ organizationId: string }>;
};

const DEFAULT_DASHBOARD_NAME = 'Untitled dashboard';
const TERMINAL_JOB_STATUSES = new Set(['succeeded', 'failed', 'cancelled']);

type CopilotAgentOption = {
  id: string;
  name: string;
  description?: string | null;
};

export default function BiStudioPage({ params }: BiStudioPageProps) {
  const { selectedOrganizationId, selectedProjectId, setSelectedOrganizationId } = useWorkspaceScope();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { organizationId } = use(params);
  const projectScope = selectedProjectId || null;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  const [selectedModelId, setSelectedModelId] = useState('');
  const [fieldSearch, setFieldSearch] = useState('');
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [isGlobalConfigOpen, setIsGlobalConfigOpen] = useState(false);

  const [dashboardName, setDashboardName] = useState(DEFAULT_DASHBOARD_NAME);
  const [dashboardDescription, setDashboardDescription] = useState('');
  const [dashboardRefreshMode, setDashboardRefreshMode] = useState<'manual' | 'live'>('manual');
  const [dashboardLastRefreshedAt, setDashboardLastRefreshedAt] = useState<string | null>(null);
  const [globalFilters, setGlobalFilters] = useState<FilterDraft[]>([]);
  const [widgets, setWidgets] = useState<BiWidget[]>([]);
  const [activeWidgetId, setActiveWidgetId] = useState<string | null>(null);
  const [activeDashboardId, setActiveDashboardId] = useState<string | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState('');
  const [isDraftMode, setIsDraftMode] = useState(false);
  const [snapshotDirty, setSnapshotDirty] = useState(false);
  const [pendingAutoRefreshDashboardId, setPendingAutoRefreshDashboardId] = useState<string | null>(null);
  const [copilotPrompt, setCopilotPrompt] = useState('');
  const [selectedCopilotAgentId, setSelectedCopilotAgentId] = useState('');
  const [copilotJobId, setCopilotJobId] = useState<string | null>(null);
  const [copilotStatusMessage, setCopilotStatusMessage] = useState<string | null>(null);
  const [copilotSummary, setCopilotSummary] = useState<string | null>(null);

  const updateWidget = useCallback((id: string, updates: Partial<BiWidget>) => {
    setWidgets((current) => current.map((widget) => (widget.id === id ? { ...widget, ...updates } : widget)));
  }, []);

  const semanticModelsQuery = useQuery<SemanticModelRecord[]>({
    queryKey: ['semantic-models', organizationId, selectedProjectId],
    queryFn: () => listSemanticModels(organizationId, selectedProjectId || undefined),
    enabled: Boolean(organizationId),
  });

  const dashboardsQuery = useQuery<DashboardRecord[]>({
    queryKey: ['bi-dashboards', organizationId, selectedProjectId],
    queryFn: () => listDashboards(organizationId, selectedProjectId || undefined),
    enabled: Boolean(organizationId),
  });
  const agentDefinitionsQuery = useQuery<AgentDefinition[]>({
    queryKey: ['agent-definitions', organizationId],
    queryFn: () => fetchAgentDefinitions(organizationId),
    enabled: Boolean(organizationId),
  });

  const semanticMetaQuery = useQuery<SemanticQueryMetaResponse>({
    queryKey: ['semantic-model-meta', organizationId, selectedModelId],
    queryFn: () => fetchSemanticQueryMeta(organizationId, selectedModelId),
    enabled: Boolean(organizationId && selectedModelId),
  });

  const semanticModel = semanticMetaQuery.data?.semanticModel;
  const tableGroups = useMemo(() => buildTableGroups(semanticModel), [semanticModel]);

  const fieldLookup = useMemo(() => {
    const map = new Map<string, FieldOption>();
    tableGroups.forEach((group) => {
      [...group.dimensions, ...group.measures, ...group.segments].forEach((field) => {
        map.set(field.id, field);
      });
    });
    return map;
  }, [tableGroups]);

  const allFields = useMemo(() => Array.from(fieldLookup.values()), [fieldLookup]);
  const activeWidget = useMemo(
    () => widgets.find((widget) => widget.id === activeWidgetId) || null,
    [widgets, activeWidgetId],
  );
  const dashboardOptions = useMemo(
    () => (dashboardsQuery.data || []).map((dashboard) => ({ id: dashboard.id, name: dashboard.name })),
    [dashboardsQuery.data],
  );
  const copilotAgentOptions = useMemo(
    () => resolveEligibleCopilotAgents(agentDefinitionsQuery.data || [], selectedModelId),
    [agentDefinitionsQuery.data, selectedModelId],
  );

  const persistedWidgets = useMemo(() => widgets.map(toPersistedWidget), [widgets]);
  const currentSnapshot = useMemo(
    () =>
      serializeDashboardState({
        name: dashboardName,
        description: dashboardDescription,
        refreshMode: dashboardRefreshMode,
        semanticModelId: selectedModelId,
        globalFilters,
        widgets: persistedWidgets,
      }),
    [dashboardName, dashboardDescription, dashboardRefreshMode, selectedModelId, globalFilters, persistedWidgets],
  );

  const hasDraftContent =
    dashboardName.trim() !== DEFAULT_DASHBOARD_NAME ||
    dashboardDescription.trim().length > 0 ||
    globalFilters.length > 0 ||
    persistedWidgets.length > 0;
  const dashboardDirty = activeDashboardId ? currentSnapshot !== savedSnapshot : hasDraftContent;

  const loadDashboardSnapshot = useCallback(
    async (dashboardId: string) => {
      try {
        const snapshot = await getDashboardSnapshot(organizationId, dashboardId);
        if (!snapshot) {
          return;
        }
        setDashboardLastRefreshedAt(snapshot.capturedAt);
        setWidgets((current) => applyDashboardSnapshotToWidgets(current, snapshot.data));
      } catch {
        // Ignore snapshot read failures and keep dashboard definition usable.
      }
    },
    [organizationId],
  );

  const createDashboardMutation = useMutation<DashboardRecord, Error, DashboardCreatePayload>({
    mutationFn: (payload) => createDashboard(organizationId, payload),
    onSuccess: async (dashboard) => {
      applyDashboardRecord(dashboard);
      setIsDraftMode(false);
      await queryClient.invalidateQueries({
        queryKey: ['bi-dashboards', organizationId, selectedProjectId],
      });
      toast({ title: 'Dashboard saved', description: 'The dashboard was created successfully.' });
    },
    onError: (error) => {
      toast({ title: 'Unable to save dashboard', description: error.message, variant: 'destructive' });
    },
  });

  const applyDashboardRecord = useCallback((dashboard: DashboardRecord) => {
    const hydratedFilters = normalizeFilters(dashboard.globalFilters);
    const hydratedWidgets = normalizeWidgets(dashboard.widgets);
    const refreshMode = dashboard.refreshMode || 'manual';

    setActiveDashboardId(dashboard.id);
    setDashboardName(dashboard.name);
    setDashboardDescription(dashboard.description || '');
    setDashboardRefreshMode(refreshMode);
    setDashboardLastRefreshedAt(dashboard.lastRefreshedAt || null);
    setSelectedModelId(dashboard.semanticModelId);
    setGlobalFilters(hydratedFilters);
    setWidgets(hydratedWidgets);
    setActiveWidgetId(hydratedWidgets[0]?.id ?? null);
    setSnapshotDirty(false);
    setPendingAutoRefreshDashboardId(refreshMode === 'live' ? dashboard.id : null);
    setSavedSnapshot(
      serializeDashboardState({
        name: dashboard.name,
        description: dashboard.description || '',
        refreshMode,
        semanticModelId: dashboard.semanticModelId,
        globalFilters: hydratedFilters,
        widgets: hydratedWidgets.map(toPersistedWidget),
      }),
    );
    void loadDashboardSnapshot(dashboard.id);
  }, [loadDashboardSnapshot]);

  const startDraftDashboard = useCallback(() => {
    setIsDraftMode(true);
    setActiveDashboardId(null);
    setDashboardName(DEFAULT_DASHBOARD_NAME);
    setDashboardDescription('');
    setDashboardRefreshMode('manual');
    setDashboardLastRefreshedAt(null);
    setGlobalFilters([]);
    setWidgets([]);
    setActiveWidgetId(null);
    setSnapshotDirty(false);
    setPendingAutoRefreshDashboardId(null);
    setSavedSnapshot('');
  }, []);

  const updateDashboardMutation = useMutation<
    DashboardRecord,
    Error,
    { dashboardId: string; payload: DashboardUpdatePayload }
  >({
    mutationFn: ({ dashboardId, payload }) => updateDashboard(organizationId, dashboardId, payload),
    onSuccess: async (dashboard) => {
      applyDashboardRecord(dashboard);
      setIsDraftMode(false);
      await queryClient.invalidateQueries({
        queryKey: ['bi-dashboards', organizationId, selectedProjectId],
      });
      toast({ title: 'Dashboard updated', description: 'Your changes have been saved.' });
    },
    onError: (error) => {
      toast({ title: 'Unable to update dashboard', description: error.message, variant: 'destructive' });
    },
  });

  const deleteDashboardMutation = useMutation<void, Error, string>({
    mutationFn: (dashboardId) => deleteDashboard(organizationId, dashboardId),
    onSuccess: async () => {
      setActiveDashboardId(null);
      setSavedSnapshot('');
      setIsDraftMode(false);
      setDashboardLastRefreshedAt(null);
      await queryClient.invalidateQueries({
        queryKey: ['bi-dashboards', organizationId, selectedProjectId],
      });
      toast({ title: 'Dashboard deleted', description: 'The dashboard has been removed.' });
    },
    onError: (error) => {
      toast({ title: 'Unable to delete dashboard', description: error.message, variant: 'destructive' });
    },
  });

  const dashboardSnapshotMutation = useMutation<
    DashboardSnapshotRecord,
    Error,
    { dashboardId: string; payload: DashboardSnapshotUpsertPayload }
  >({
    mutationFn: ({ dashboardId, payload }) => upsertDashboardSnapshot(organizationId, dashboardId, payload),
    onSuccess: (snapshot) => {
      setDashboardLastRefreshedAt(snapshot.capturedAt);
    },
  });

  const queryMutation = useMutation<
    SemanticQueryJobResponse,
    Error,
    { widgetId: string; payload: SemanticQueryRequestPayload }
  >({
    mutationFn: async ({ payload }) => enqueueSemanticQuery(organizationId, payload),
    onMutate: ({ widgetId }) => {
      updateWidget(widgetId, {
        queryResult: null,
        isLoading: true,
        jobId: null,
        jobStatus: 'queued',
        progress: 0,
        statusMessage: 'Queued for execution.',
        error: null,
      });
    },
    onSuccess: (data, { widgetId }) => {
      updateWidget(widgetId, {
        isLoading: true,
        jobId: data.jobId,
        jobStatus: data.jobStatus,
        progress: 5,
        statusMessage: 'Semantic query job accepted.',
      });
    },
    onError: (error, { widgetId }) => {
      updateWidget(widgetId, {
        isLoading: false,
        jobId: null,
        jobStatus: 'failed',
        progress: 0,
        statusMessage: 'Unable to queue semantic query.',
        error: error.message,
      });
    },
  });
  const copilotMutation = useMutation<DashboardCopilotJobResponsePayload, Error, string>({
    mutationFn: (instructions) =>
      enqueueDashboardCopilotJob(organizationId, selectedCopilotAgentId, {
        projectId: projectScope,
        semanticModelId: selectedModelId,
        instructions,
        dashboardName: dashboardName.trim() || null,
        currentDashboard: {
          name: dashboardName,
          description: dashboardDescription,
          refreshMode: dashboardRefreshMode,
          semanticModelId: selectedModelId,
          globalFilters: globalFilters.map((filter) => ({ ...filter })),
          widgets: persistedWidgets.map((widget) => ({ ...widget })),
        },
        generatePreviews: true,
        maxWidgets: 6,
      }),
    onMutate: () => {
      setCopilotSummary(null);
      setCopilotStatusMessage('Copilot request queued.');
    },
    onSuccess: (response) => {
      setCopilotJobId(response.jobId);
      setCopilotStatusMessage('Copilot job accepted.');
    },
    onError: (error) => {
      setCopilotJobId(null);
      setCopilotStatusMessage(error.message);
      toast({
        title: 'Unable to start BI copilot',
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  useEffect(() => {
    if (semanticModelsQuery.data?.length && !selectedModelId) {
      setSelectedModelId(semanticModelsQuery.data[0].id);
    }
  }, [semanticModelsQuery.data, selectedModelId]);

  useEffect(() => {
    if (copilotAgentOptions.length === 0) {
      if (selectedCopilotAgentId) {
        setSelectedCopilotAgentId('');
      }
      return;
    }
    if (!selectedCopilotAgentId || !copilotAgentOptions.some((agent) => agent.id === selectedCopilotAgentId)) {
      setSelectedCopilotAgentId(copilotAgentOptions[0].id);
    }
  }, [copilotAgentOptions, selectedCopilotAgentId]);

  useEffect(() => {
    const dashboards = dashboardsQuery.data;
    if (!dashboards) {
      return;
    }
    if (dashboards.length === 0) {
      if (!isDraftMode) {
        startDraftDashboard();
      }
      return;
    }
    if (isDraftMode) {
      return;
    }
    if (activeDashboardId) {
      const activeDashboard = dashboards.find((dashboard) => dashboard.id === activeDashboardId);
      if (activeDashboard) {
        return;
      }
    }
    applyDashboardRecord(dashboards[0]);
  }, [dashboardsQuery.data, activeDashboardId, isDraftMode, startDraftDashboard, applyDashboardRecord]);

  useEffect(() => {
    const pendingWidgets = widgets.filter(
      (widget) => widget.isLoading && widget.jobId && !isTerminalJobStatus(widget.jobStatus),
    );
    if (pendingWidgets.length === 0) {
      return;
    }

    let cancelled = false;
    const pollJobs = async () => {
      await Promise.all(
        pendingWidgets.map(async (widget) => {
          if (!widget.jobId) {
            return;
          }
          try {
            const job = await fetchAgentJobState(organizationId, widget.jobId, false);
            if (cancelled) {
              return;
            }
            const latestMessage = job.events[job.events.length - 1]?.message ?? `Status: ${job.status}`;
            const progress = Math.max(0, Math.min(100, job.progress ?? 0));

            if (job.status === 'failed' || job.status === 'cancelled') {
              updateWidget(widget.id, {
                isLoading: false,
                jobStatus: job.status,
                progress,
                statusMessage: latestMessage,
                error: getErrorMessage(job.error, 'Semantic query failed.'),
              });
              return;
            }

            if (job.status === 'succeeded') {
              const result = normalizeSemanticQueryResponse(job.finalResponse?.result);
              if (!result) {
                updateWidget(widget.id, {
                  isLoading: false,
                  jobStatus: 'failed',
                  progress: 100,
                  statusMessage: 'Semantic query completed without result payload.',
                  error: 'Semantic query job completed without a valid result.',
                });
                return;
              }

              updateWidget(widget.id, {
                isLoading: false,
                queryResult: result,
                jobStatus: job.status,
                progress: 100,
                statusMessage: latestMessage,
                error: null,
              });
              setSnapshotDirty(true);
              return;
            }

            updateWidget(widget.id, {
              isLoading: true,
              jobStatus: job.status,
              progress,
              statusMessage: latestMessage,
              error: null,
            });
          } catch {
            if (cancelled) {
              return;
            }
          }
        }),
      );
    };

    void pollJobs();
    const intervalId = window.setInterval(() => {
      void pollJobs();
    }, 1250);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [organizationId, updateWidget, widgets]);

  useEffect(() => {
    if (!copilotJobId) {
      return;
    }
    let cancelled = false;

    const pollCopilotJob = async () => {
      try {
        const job = await fetchAgentJobState(organizationId, copilotJobId, false);
        if (cancelled) {
          return;
        }

        const latestMessage = job.events[job.events.length - 1]?.message ?? `Status: ${job.status}`;
        setCopilotStatusMessage(latestMessage);

        if (job.status === 'failed' || job.status === 'cancelled') {
          setCopilotJobId(null);
          const errorMessage = getErrorMessage(job.error, 'BI copilot job failed.');
          setCopilotStatusMessage(errorMessage);
          toast({
            title: 'BI copilot failed',
            description: errorMessage,
            variant: 'destructive',
          });
          return;
        }

        if (job.status !== 'succeeded') {
          return;
        }

        const result = normalizeCopilotDashboardResult(job.finalResponse?.result);
        if (!result) {
          setCopilotJobId(null);
          setCopilotStatusMessage('Copilot job completed without a valid dashboard payload.');
          toast({
            title: 'BI copilot result unavailable',
            description: 'The copilot response did not include a valid dashboard payload.',
            variant: 'destructive',
          });
          return;
        }

        const appliedWidgets = normalizeCopilotWidgets(result.widgets);
        const appliedFilters = normalizeFilters(result.globalFilters);

        setGlobalFilters(appliedFilters);
        setWidgets(appliedWidgets);
        setActiveWidgetId(appliedWidgets[0]?.id ?? null);
        setSnapshotDirty(appliedWidgets.some((widget) => Boolean(widget.queryResult)));
        setCopilotSummary(result.summary || job.finalResponse?.summary || latestMessage);
        setCopilotStatusMessage('Copilot dashboard applied.');
        setCopilotPrompt('');
        setCopilotJobId(null);
      } catch {
        if (cancelled) {
          return;
        }
      }
    };

    void pollCopilotJob();
    const intervalId = window.setInterval(() => {
      void pollCopilotJob();
    }, 1250);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [copilotJobId, organizationId, toast]);

  useEffect(() => {
    if (!snapshotDirty || !activeDashboardId || isDraftMode) {
      return;
    }
    if (widgets.some((widget) => widget.isLoading)) {
      return;
    }
    const snapshotData = buildDashboardSnapshotData(widgets);
    if (!hasSnapshotData(snapshotData)) {
      setSnapshotDirty(false);
      return;
    }
    dashboardSnapshotMutation.mutate({
      dashboardId: activeDashboardId,
      payload: {
        data: snapshotData,
        capturedAt: new Date().toISOString(),
      },
    });
    setSnapshotDirty(false);
  }, [activeDashboardId, dashboardSnapshotMutation, isDraftMode, snapshotDirty, widgets]);

  useEffect(() => {
    if (
      !pendingAutoRefreshDashboardId ||
      pendingAutoRefreshDashboardId !== activeDashboardId ||
      dashboardRefreshMode !== 'live'
    ) {
      return;
    }
    if (!selectedModelId) {
      return;
    }
    const runnable = widgets.filter((widget) => widget.dimensions.length > 0 || widget.measures.length > 0);
    if (runnable.length === 0) {
      setPendingAutoRefreshDashboardId(null);
      return;
    }
    runnable.forEach((widget) => {
      const payload = buildWidgetQueryPayload({
        widget,
        organizationId,
        projectId: projectScope,
        semanticModelId: selectedModelId,
        globalFilters,
      });
      queryMutation.mutate({ widgetId: widget.id, payload });
    });
    setPendingAutoRefreshDashboardId(null);
  }, [
    activeDashboardId,
    dashboardRefreshMode,
    globalFilters,
    organizationId,
    pendingAutoRefreshDashboardId,
    projectScope,
    queryMutation,
    selectedModelId,
    widgets,
  ]);

  const handleAddWidget = () => {
    const widget = buildEmptyWidget(widgets.length + 1);
    setWidgets((current) => [...current, widget]);
    setActiveWidgetId(widget.id);
    setIsConfigOpen(true);
  };

  const handleDuplicateWidget = (widgetId: string) => {
    const source = widgets.find((widget) => widget.id === widgetId);
    if (!source) {
      return;
    }
    const copy: BiWidget = {
      ...source,
      id: makeLocalId(),
      title: `${source.title} copy`,
      queryResult: null,
      isLoading: false,
      jobId: null,
      jobStatus: null,
      progress: 0,
      statusMessage: null,
      error: null,
    };
    setWidgets((current) => [...current, copy]);
    setActiveWidgetId(copy.id);
    setIsConfigOpen(true);
  };

  const handleRemoveWidget = (id: string) => {
    setWidgets((current) => current.filter((widget) => widget.id !== id));
    if (activeWidgetId === id) {
      setActiveWidgetId(null);
    }
  };

  const handleAddFieldToWidget = (
    widgetId: string,
    field: FieldOption,
    targetKind?: 'dimension' | 'measure',
  ) => {
    const widget = widgets.find((candidate) => candidate.id === widgetId);
    if (!widget) {
      return;
    }

    const kind = targetKind || (field.kind === 'measure' || field.kind === 'metric' ? 'measure' : 'dimension');
    if (kind === 'dimension' && !widget.dimensions.includes(field.id)) {
      updateWidget(widgetId, { dimensions: [...widget.dimensions, field.id] });
    }
    if (kind === 'measure' && !widget.measures.includes(field.id)) {
      updateWidget(widgetId, { measures: [...widget.measures, field.id] });
    }
    setActiveWidgetId(widgetId);
  };

  const handleRemoveFieldFromWidget = (widgetId: string, fieldId: string, kind: 'dimension' | 'measure') => {
    const widget = widgets.find((candidate) => candidate.id === widgetId);
    if (!widget) {
      return;
    }
    if (kind === 'dimension') {
      updateWidget(widgetId, { dimensions: widget.dimensions.filter((id) => id !== fieldId) });
      return;
    }
    updateWidget(widgetId, { measures: widget.measures.filter((id) => id !== fieldId) });
  };

  const handleSidebarAddField = (field: FieldOption) => {
    if (activeWidgetId) {
      handleAddFieldToWidget(activeWidgetId, field);
      return;
    }
    const kind = field.kind === 'measure' || field.kind === 'metric' ? 'measure' : 'dimension';
    const widget = buildEmptyWidget(widgets.length + 1);
    widget.dimensions = kind === 'dimension' ? [field.id] : [];
    widget.measures = kind === 'measure' ? [field.id] : [];
    setWidgets((current) => [...current, widget]);
    setActiveWidgetId(widget.id);
    setIsConfigOpen(true);
  };

  const handleRunQuery = () => {
    if (!activeWidget || !selectedModelId) {
      return;
    }
    const payload = buildWidgetQueryPayload({
      widget: activeWidget,
      organizationId,
      projectId: projectScope,
      semanticModelId: selectedModelId,
      globalFilters,
    });
    queryMutation.mutate({ widgetId: activeWidget.id, payload });
  };

  const handleRunAllQueries = () => {
    if (!selectedModelId) {
      return;
    }
    widgets.forEach((widget) => {
      if (widget.dimensions.length === 0 && widget.measures.length === 0) {
        return;
      }
      const payload = buildWidgetQueryPayload({
        widget,
        organizationId,
        projectId: projectScope,
        semanticModelId: selectedModelId,
        globalFilters,
      });
      queryMutation.mutate({ widgetId: widget.id, payload });
    });
  };

  const handleExportCsv = () => {
    if (!activeWidget?.queryResult?.data?.length) {
      return;
    }
    const rows = activeWidget.queryResult.data;
    const firstRow = rows[0];
    const columns = Object.keys(firstRow);
    const csvContent = [
      columns.join(','),
      ...rows.map((row) => columns.map((column) => String(row[column] ?? '')).join(',')),
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${activeWidget.title.replace(/\s+/g, '_')}_export.csv`;
    link.click();
  };

  const handleCreateDashboard = () => {
    startDraftDashboard();
  };

  const handleSelectDashboard = (dashboardId: string) => {
    if (!dashboardId) {
      handleCreateDashboard();
      return;
    }
    const dashboard = (dashboardsQuery.data || []).find((item) => item.id === dashboardId);
    if (!dashboard) {
      return;
    }
    setIsDraftMode(false);
    applyDashboardRecord(dashboard);
  };

  const handleSaveDashboard = () => {
    const normalizedName = dashboardName.trim();
    if (!normalizedName) {
      toast({ title: 'Dashboard name is required', variant: 'destructive' });
      return;
    }
    if (!selectedModelId) {
      toast({
        title: 'Select a semantic model',
        description: 'Dashboards must be saved against a semantic model.',
        variant: 'destructive',
      });
      return;
    }

    const payload: DashboardCreatePayload = {
      projectId: projectScope,
      semanticModelId: selectedModelId,
      name: normalizedName,
      description: dashboardDescription.trim() || null,
      refreshMode: dashboardRefreshMode,
      globalFilters: globalFilters.map((filter) => ({ ...filter })),
      widgets: persistedWidgets.map((widget) => ({ ...widget })),
    };

    if (activeDashboardId && !isDraftMode) {
      updateDashboardMutation.mutate({ dashboardId: activeDashboardId, payload });
      return;
    }
    createDashboardMutation.mutate(payload);
  };

  const handleDeleteDashboard = () => {
    if (!activeDashboardId || isDraftMode) {
      return;
    }
    deleteDashboardMutation.mutate(activeDashboardId);
  };

  const handleRunCopilot = () => {
    const instructions = copilotPrompt.trim();
    if (!instructions) {
      return;
    }
    if (!selectedModelId) {
      toast({
        title: 'Select a semantic model',
        description: 'Copilot requires an active semantic model.',
        variant: 'destructive',
      });
      return;
    }
    if (!selectedCopilotAgentId) {
      toast({
        title: 'Select a copilot agent',
        description: 'No BI copilot-enabled agent is currently available for this semantic model.',
        variant: 'destructive',
      });
      return;
    }
    if (copilotJobId) {
      return;
    }
    copilotMutation.mutate(instructions);
  };

  if (!organizationId) {
    return <div className="p-10 text-center">Select an organization to continue.</div>;
  }

  const isAnyRunning = widgets.some((widget) => widget.isLoading);
  const isCopilotRunning = copilotMutation.isPending || Boolean(copilotJobId);
  const isSavingDashboard = createDashboardMutation.isPending || updateDashboardMutation.isPending;
  const canRunActive = !!activeWidget && (activeWidget.dimensions.length > 0 || activeWidget.measures.length > 0);
  const canRunAll = widgets.some((widget) => widget.dimensions.length > 0 || widget.measures.length > 0);

  return (
    <div className="flex h-[calc(100vh-4rem)] w-full overflow-hidden relative p-4 gap-4">
      <BiSidebar
        semanticModels={semanticModelsQuery.data || []}
        selectedModelId={selectedModelId}
        onSelectModel={setSelectedModelId}
        tableGroups={tableGroups}
        fieldSearch={fieldSearch}
        onFieldSearchChange={setFieldSearch}
        onAddField={handleSidebarAddField}
        selectedFields={new Set([...(activeWidget?.dimensions || []), ...(activeWidget?.measures || [])])}
      />

      <div className="flex-1 flex flex-col rounded-[2.5rem] bg-[color:var(--panel-bg)] border border-[color:var(--panel-border)] shadow-soft overflow-hidden relative">
        <BiHeader
          dashboards={dashboardOptions}
          activeDashboardId={isDraftMode ? null : activeDashboardId}
          onSelectDashboard={handleSelectDashboard}
          onCreateDashboard={handleCreateDashboard}
          onSaveDashboard={handleSaveDashboard}
          onDeleteDashboard={handleDeleteDashboard}
          canDeleteDashboard={Boolean(activeDashboardId) && !isDraftMode && !deleteDashboardMutation.isPending}
          isSavingDashboard={isSavingDashboard}
          dashboardDirty={dashboardDirty}
          onRunActive={handleRunQuery}
          onRunAll={handleRunAllQueries}
          onToggleGlobalConfig={() => {
            setIsGlobalConfigOpen(!isGlobalConfigOpen);
            if (!isGlobalConfigOpen) {
              setIsConfigOpen(false);
            }
          }}
          isRunning={isAnyRunning}
          canRunActive={canRunActive}
          canRunAll={canRunAll}
          onToggleConfig={() => {
            setIsConfigOpen(!isConfigOpen);
            if (!isConfigOpen) {
              setIsGlobalConfigOpen(false);
            }
          }}
          title={dashboardName}
        />

        <BiCanvas
          widgets={widgets}
          activeWidgetId={activeWidgetId}
          onActivateWidget={(id) => {
            setActiveWidgetId(id);
            setIsConfigOpen(true);
          }}
          onRemoveWidget={handleRemoveWidget}
          onDuplicateWidget={handleDuplicateWidget}
          onAddWidget={handleAddWidget}
          onAddFieldToWidget={handleAddFieldToWidget}
        />

        <div
          className={`absolute top-4 right-4 bottom-4 w-80 z-50 transition-transform duration-300 ease-in-out ${
            isConfigOpen && activeWidget ? 'translate-x-0' : 'translate-x-[120%]'
          }`}
        >
          <div className="h-full rounded-3xl bg-[color:var(--panel-bg)] shadow-soft border border-[color:var(--panel-border)] overflow-hidden">
            {activeWidget ? (
              <BiConfigPanel
                onClose={() => setIsConfigOpen(false)}
                title={activeWidget.title}
                setTitle={(title) => updateWidget(activeWidget.id, { title })}
                chartX={activeWidget.chartX}
                setChartX={(x) => updateWidget(activeWidget.id, { chartX: x })}
                chartY={activeWidget.chartY}
                setChartY={(y) => updateWidget(activeWidget.id, { chartY: y })}
                chartType={activeWidget.type}
                setChartType={(type) => updateWidget(activeWidget.id, { type })}
                widgetSize={activeWidget.size}
                setWidgetSize={(size) => updateWidget(activeWidget.id, { size })}
                fields={allFields}
                selectedDimensions={activeWidget.dimensions}
                selectedMeasures={activeWidget.measures}
                onRemoveField={(id, kind) => handleRemoveFieldFromWidget(activeWidget.id, id, kind)}
                filters={activeWidget.filters}
                setFilters={(filters) => updateWidget(activeWidget.id, { filters })}
                orderBys={activeWidget.orderBys}
                setOrderBys={(orderBys) => updateWidget(activeWidget.id, { orderBys })}
                limit={activeWidget.limit}
                setLimit={(limit) => updateWidget(activeWidget.id, { limit })}
                timeDimension={activeWidget.timeDimension}
                setTimeDimension={(id) => updateWidget(activeWidget.id, { timeDimension: id })}
                timeGrain={activeWidget.timeGrain}
                setTimeGrain={(grain) => updateWidget(activeWidget.id, { timeGrain: grain })}
                timeRangePreset={activeWidget.timeRangePreset}
                setTimeRangePreset={(preset) => updateWidget(activeWidget.id, { timeRangePreset: preset })}
                onExportCsv={handleExportCsv}
                onShowSql={() => toast({ title: 'SQL preview', description: 'SQL preview is coming soon.' })}
              />
            ) : null}
          </div>
        </div>

        <div
          className={`absolute top-4 right-4 bottom-4 w-80 z-40 transition-transform duration-300 ease-in-out ${
            isGlobalConfigOpen ? 'translate-x-0' : 'translate-x-[120%]'
          }`}
        >
          <div className="h-full rounded-3xl bg-[color:var(--panel-bg)] shadow-soft border border-[color:var(--panel-border)] overflow-hidden">
            <BiGlobalConfigPanel
              onClose={() => setIsGlobalConfigOpen(false)}
              dashboardName={dashboardName}
              setDashboardName={setDashboardName}
              dashboardDescription={dashboardDescription}
              setDashboardDescription={setDashboardDescription}
              refreshMode={dashboardRefreshMode}
              setRefreshMode={setDashboardRefreshMode}
              lastRefreshedAt={dashboardLastRefreshedAt}
              fields={allFields}
              globalFilters={globalFilters}
              setGlobalFilters={setGlobalFilters}
              onApplyGlobalFilters={handleRunAllQueries}
            />
          </div>
        </div>
      </div>

      <BiAiInput
        agents={copilotAgentOptions}
        selectedAgentId={selectedCopilotAgentId}
        onSelectAgent={setSelectedCopilotAgentId}
        prompt={copilotPrompt}
        onPromptChange={setCopilotPrompt}
        onSubmit={handleRunCopilot}
        isRunning={isCopilotRunning}
        statusMessage={copilotStatusMessage}
        summary={copilotSummary}
      />
    </div>
  );
}

function resolveEligibleCopilotAgents(
  agents: AgentDefinition[],
  semanticModelId: string,
): CopilotAgentOption[] {
  if (!semanticModelId) {
    return [];
  }
  return agents
    .filter((agent) => agent.isActive)
    .flatMap((agent) => {
      const definition = toRecord(agent.definition);
      if (!definition) {
        return [];
      }
      const features = toRecord(definition.features);
      const biCopilotEnabled =
        (features?.bi_copilot_enabled === true || features?.biCopilotEnabled === true) ?? false;
      if (!features || !biCopilotEnabled) {
        return [];
      }

      const tools = Array.isArray(definition.tools) ? definition.tools : [];
      const hasSemanticBinding = tools.some((tool) => {
        const toolRecord = toRecord(tool);
        if (!toolRecord) {
          return false;
        }
        const toolType = readString(toolRecord.tool_type) ?? readString(toolRecord.toolType);
        const toolName = (readString(toolRecord.name) || '').toLowerCase();
        const isSqlTool = toolType === 'sql' || toolName.includes('sql');
        if (!isSqlTool) {
          return false;
        }
        const config = toRecord(toolRecord.config);
        if (!config) {
          return false;
        }
        const definitionId = readString(config.definition_id) ?? readString(config.definitionId);
        return definitionId === semanticModelId;
      });

      if (!hasSemanticBinding) {
        return [];
      }
      return [{ id: agent.id, name: agent.name, description: agent.description ?? null }];
    });
}

function normalizeCopilotDashboardResult(value: unknown): {
  summary: string | null;
  globalFilters: Array<Record<string, unknown>>;
  widgets: Array<Record<string, unknown>>;
} | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  return {
    summary: readString(payload.summary),
    globalFilters: asRecordArray(payload.globalFilters),
    widgets: asRecordArray(payload.widgets),
  };
}

function normalizeCopilotWidgets(value: Array<Record<string, unknown>>): BiWidget[] {
  return value.map((entry, index) => {
    const id = typeof entry.id === 'string' && entry.id.length > 0 ? entry.id : makeLocalId();
    const title =
      typeof entry.title === 'string' && entry.title.trim().length > 0
        ? entry.title
        : `Analysis ${index + 1}`;
    return {
      id,
      title,
      type: normalizeChartType(entry.type),
      size: normalizeWidgetSize(entry.size),
      measures: toStringArray(entry.measures),
      dimensions: toStringArray(entry.dimensions),
      filters: normalizeFilters(asRecordArray(entry.filters)),
      orderBys: normalizeOrderBys(asRecordArray(entry.orderBys)),
      limit: normalizeNumber(entry.limit, 500),
      timeDimension: normalizeString(entry.timeDimension),
      timeGrain: normalizeString(entry.timeGrain),
      timeRangePreset: normalizeString(entry.timeRangePreset),
      chartX: normalizeString(entry.chartX),
      chartY: normalizeString(entry.chartY),
      queryResult: normalizeSemanticQueryResponse(entry.queryResult),
      isLoading: false,
      jobId: null,
      jobStatus: readString(entry.jobStatus),
      progress: normalizeNumber(entry.progress, 0),
      statusMessage: readString(entry.statusMessage),
      error: readString(entry.error),
    };
  });
}

function buildEmptyWidget(sequence: number): BiWidget {
  return {
    id: makeLocalId(),
    title: `Analysis ${sequence}`,
    type: 'bar',
    size: 'small',
    measures: [],
    dimensions: [],
    filters: [],
    orderBys: [],
    limit: 500,
    timeDimension: '',
    timeGrain: '',
    timeRangePreset: '',
    chartX: '',
    chartY: '',
    queryResult: null,
    isLoading: false,
    jobId: null,
    jobStatus: null,
    progress: 0,
    statusMessage: null,
    error: null,
  };
}

function makeLocalId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 11);
}

function toPersistedWidget(widget: BiWidget): PersistedBiWidget {
  return {
    id: widget.id,
    title: widget.title,
    type: widget.type,
    size: widget.size,
    measures: [...widget.measures],
    dimensions: [...widget.dimensions],
    filters: widget.filters.map((filter) => ({ ...filter })),
    orderBys: widget.orderBys.map((order) => ({ ...order })),
    limit: widget.limit,
    timeDimension: widget.timeDimension,
    timeGrain: widget.timeGrain,
    timeRangePreset: widget.timeRangePreset,
    chartX: widget.chartX,
    chartY: widget.chartY,
  };
}

function normalizeFilters(value: Array<Record<string, unknown>>): FilterDraft[] {
  return value
    .map((filter, index) => {
      const member = typeof filter.member === 'string' ? filter.member : '';
      const operator = typeof filter.operator === 'string' ? filter.operator : 'equals';
      const values = typeof filter.values === 'string' ? filter.values : '';
      if (!member) {
        return null;
      }
      return {
        id: typeof filter.id === 'string' ? filter.id : `${member}-${index}`,
        member,
        operator,
        values,
      };
    })
    .filter((filter): filter is FilterDraft => Boolean(filter));
}

function normalizeWidgets(value: Array<Record<string, unknown>>): BiWidget[] {
  return value.map((entry, index) => {
    const id = typeof entry.id === 'string' && entry.id.length > 0 ? entry.id : makeLocalId();
    const title =
      typeof entry.title === 'string' && entry.title.trim().length > 0
        ? entry.title
        : `Analysis ${index + 1}`;
    return {
      id,
      title,
      type: normalizeChartType(entry.type),
      size: normalizeWidgetSize(entry.size),
      measures: toStringArray(entry.measures),
      dimensions: toStringArray(entry.dimensions),
      filters: normalizeFilters(asRecordArray(entry.filters)),
      orderBys: normalizeOrderBys(asRecordArray(entry.orderBys)),
      limit: normalizeNumber(entry.limit, 500),
      timeDimension: normalizeString(entry.timeDimension),
      timeGrain: normalizeString(entry.timeGrain),
      timeRangePreset: normalizeString(entry.timeRangePreset),
      chartX: normalizeString(entry.chartX),
      chartY: normalizeString(entry.chartY),
      queryResult: null,
      isLoading: false,
      jobId: null,
      jobStatus: null,
      progress: 0,
      statusMessage: null,
      error: null,
    };
  });
}

function normalizeOrderBys(value: Array<Record<string, unknown>>) {
  return value
    .map((order, index) => {
      const member = typeof order.member === 'string' ? order.member : '';
      if (!member) {
        return null;
      }
      const direction = order.direction === 'asc' ? 'asc' : 'desc';
      return {
        id: typeof order.id === 'string' ? order.id : `order-${index}`,
        member,
        direction,
      };
    })
    .filter((order): order is { id: string; member: string; direction: 'asc' | 'desc' } => Boolean(order));
}

function normalizeChartType(value: unknown): BiWidget['type'] {
  if (value === 'line' || value === 'pie' || value === 'table') {
    return value;
  }
  return 'bar';
}

function normalizeWidgetSize(value: unknown): BiWidget['size'] {
  if (value === 'wide' || value === 'tall' || value === 'large') {
    return value;
  }
  return 'small';
}

function normalizeNumber(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return fallback;
  }
  return value;
}

function normalizeString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'));
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string' && item.length > 0);
}

function serializeDashboardState(input: {
  name: string;
  description: string;
  refreshMode: 'manual' | 'live';
  semanticModelId: string;
  globalFilters: FilterDraft[];
  widgets: PersistedBiWidget[];
}): string {
  return JSON.stringify({
    name: input.name.trim(),
    description: input.description.trim(),
    refreshMode: input.refreshMode,
    semanticModelId: input.semanticModelId,
    globalFilters: input.globalFilters.map((filter) => ({
      member: filter.member,
      operator: filter.operator,
      values: filter.values,
    })),
    widgets: input.widgets,
  });
}

function buildWidgetQueryPayload(input: {
  widget: BiWidget;
  organizationId: string;
  projectId: string | null;
  semanticModelId: string;
  globalFilters: FilterDraft[];
}): SemanticQueryRequestPayload {
  const timeDimensionsPayload = input.widget.timeDimension
    ? [
        {
          dimension: input.widget.timeDimension,
          granularity: input.widget.timeGrain || undefined,
          dateRange: input.widget.timeRangePreset || undefined,
        },
      ]
    : [];
  const filterPayload = buildSemanticFilters([...input.globalFilters, ...input.widget.filters]);
  const orderPayload =
    input.widget.orderBys.length > 0
      ? input.widget.orderBys.map((order) => ({ [order.member]: order.direction }))
      : undefined;

  return {
    organizationId: input.organizationId,
    projectId: input.projectId,
    semanticModelId: input.semanticModelId,
    query: {
      measures: input.widget.measures,
      dimensions: input.widget.dimensions,
      timeDimensions: timeDimensionsPayload,
      filters: filterPayload.length > 0 ? filterPayload : undefined,
      order: orderPayload,
      limit: input.widget.limit,
    },
  };
}

function buildSemanticFilters(filters: FilterDraft[]) {
  return filters.flatMap((filter) => {
    const member = filter.member.trim();
    if (!member) {
      return [];
    }
    const operator = filter.operator.trim() || 'equals';
    if (operator === 'set' || operator === 'notset') {
      return [{ member, operator }];
    }
    const values = filter.values
      .split(',')
      .map((value) => value.trim())
      .filter((value) => value.length > 0);
    if (values.length === 0) {
      return [];
    }
    return [{ member, operator, values }];
  });
}

function isTerminalJobStatus(status: string | null | undefined): boolean {
  if (!status) {
    return false;
  }
  return TERMINAL_JOB_STATUSES.has(status);
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return fallback;
}

function normalizeSemanticQueryResponse(value: unknown): SemanticQueryResponse | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const id = readString(payload.id);
  const organizationId = readString(payload.organizationId) ?? readString(payload.organization_id);
  const semanticModelId = readString(payload.semanticModelId) ?? readString(payload.semantic_model_id);
  if (!id || !organizationId || !semanticModelId) {
    return null;
  }
  return {
    id,
    organizationId,
    projectId: readString(payload.projectId) ?? readString(payload.project_id) ?? null,
    semanticModelId,
    data: toRecordArray(payload.data),
    annotations: toRecordArray(payload.annotations),
    metadata: Array.isArray(payload.metadata) ? toRecordArray(payload.metadata) : undefined,
  };
}

function readString(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function toRecordArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'));
}

function buildDashboardSnapshotData(widgets: BiWidget[]): Record<string, unknown> {
  const capturedAt = new Date().toISOString();
  const widgetResults: Record<string, unknown> = {};
  widgets.forEach((widget) => {
    if (!widget.queryResult) {
      return;
    }
    widgetResults[widget.id] = {
      refreshed_at: capturedAt,
      result: widget.queryResult,
    };
  });
  return {
    version: 1,
    captured_at: capturedAt,
    widgets: widgetResults,
  };
}

function hasSnapshotData(snapshot: Record<string, unknown>): boolean {
  const widgets = snapshot.widgets;
  return Boolean(widgets && typeof widgets === 'object' && Object.keys(widgets as Record<string, unknown>).length > 0);
}

function applyDashboardSnapshotToWidgets(
  widgets: BiWidget[],
  snapshot: Record<string, unknown>,
): BiWidget[] {
  const widgetPayload = snapshot.widgets;
  if (!widgetPayload || typeof widgetPayload !== 'object') {
    return widgets;
  }
  const widgetMap = widgetPayload as Record<string, unknown>;
  return widgets.map((widget) => {
    if (widget.isLoading) {
      return widget;
    }
    const entry = widgetMap[widget.id];
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      return widget;
    }
    const parsed = normalizeSemanticQueryResponse((entry as Record<string, unknown>).result);
    if (!parsed) {
      return widget;
    }
    return {
      ...widget,
      queryResult: parsed,
      isLoading: false,
      jobId: null,
      jobStatus: null,
      progress: 100,
      statusMessage: 'Loaded from cached snapshot.',
      error: null,
    };
  });
}

function buildTableGroups(semanticModel?: SemanticModelPayload): TableGroup[] {
  if (!semanticModel || !semanticModel.tables) {
    return [];
  }

  const groups: TableGroup[] = Object.entries(semanticModel.tables).map(([tableKey, table]) => {
    const dimensions: FieldOption[] = (table.dimensions ?? []).map((dimension) => ({
      id: dimension.full_path || `${tableKey}.${dimension.name}`,
      label: dimension.alias || dimension.name,
      kind: 'dimension',
      type: dimension.type,
      description: dimension.description,
      tableKey,
    }));

    const measures: FieldOption[] = (table.measures ?? []).map((measure) => ({
      id: measure.full_path || `${tableKey}.${measure.name}`,
      label: measure.name,
      kind: 'measure',
      type: measure.type,
      description: measure.description,
      aggregation: measure.aggregation,
      tableKey,
    }));

    const segments: FieldOption[] = table.filters
      ? Object.entries(table.filters).map(([filterName, filter]) => ({
          id: `${tableKey}.${filterName}`,
          label: filterName,
          kind: 'segment',
          description: filter.description,
          tableKey,
        }))
      : [];

    return {
      tableKey,
      schema: table.schema,
      name: table.name,
      description: table.description,
      dimensions,
      measures,
      segments,
    };
  });

  if (semanticModel.metrics) {
    groups.push({
      tableKey: 'metrics',
      schema: 'model',
      name: 'Metrics',
      dimensions: [],
      measures: Object.entries(semanticModel.metrics).map(([name, metric]) => ({
        id: name,
        label: name,
        kind: 'metric',
        type: 'number',
        description: metric.description,
        tableKey: 'metrics',
      })),
      segments: [],
    });
  }

  return groups;
}
