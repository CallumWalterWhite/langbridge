'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { listSemanticModels } from '@/orchestration/semanticModels';
import type { SemanticModelRecord } from '@/orchestration/semanticModels/types';
import { fetchSemanticQueryMeta, runSemanticQuery } from '@/orchestration/semanticQuery';
import type {
  SemanticModelPayload,
  SemanticQueryMetaResponse,
  SemanticQueryRequestPayload,
  SemanticQueryResponse,
} from '@/orchestration/semanticQuery/types';

import { BiSidebar } from '../_components/BiSidebar';
import { BiHeader } from '../_components/BiHeader';
import { BiCanvas } from '../_components/BiCanvas';
import { BiConfigPanel } from '../_components/BiConfigPanel';
import { BiAiInput } from '../_components/BiAiInput';
import { BiGlobalConfigPanel } from '../_components/BiGlobalConfigPanel';
import { 
  FieldOption, 
  TableGroup, 
  BiWidget,
  FilterDraft
} from '../types';

type BiStudioPageProps = {
  params: { organizationId: string };
};

export default function BiStudioPage({ params }: BiStudioPageProps) {
  const { selectedOrganizationId, selectedProjectId, setSelectedOrganizationId } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);
  
  // -- Global State --
  const [selectedModelId, setSelectedModelId] = useState('');
  const [fieldSearch, setFieldSearch] = useState('');
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [isGlobalConfigOpen, setIsGlobalConfigOpen] = useState(false);
  const [workspaceName, setWorkspaceName] = useState('Workspace');
  const [globalFilters, setGlobalFilters] = useState<FilterDraft[]>([]);

  // -- Multi-Widget State --
  const [widgets, setWidgets] = useState<BiWidget[]>([]);
  const [activeWidgetId, setActiveWidgetId] = useState<string | null>(null);

  // -- Data Fetching --
  const semanticModelsQuery = useQuery<SemanticModelRecord[]>({
    queryKey: ['semantic-models', organizationId, selectedProjectId],
    queryFn: () =>
      listSemanticModels(organizationId, selectedProjectId ?? undefined),
    enabled: Boolean(organizationId),
  });

  const semanticMetaQuery = useQuery<SemanticQueryMetaResponse>({
    queryKey: ['semantic-model-meta', organizationId, selectedModelId],
    queryFn: () => fetchSemanticQueryMeta(organizationId, selectedModelId),
    enabled: Boolean(organizationId && selectedModelId),
  });

  // Derived Data
  const semanticModel = semanticMetaQuery.data?.semanticModel;
  const tableGroups = useMemo(() => buildTableGroups(semanticModel), [semanticModel]);
  const fieldLookup = useMemo(() => {
    const map = new Map<string, FieldOption>();
    tableGroups.forEach(group => {
      [...group.dimensions, ...group.measures, ...group.segments].forEach(field => map.set(field.id, field));
    });
    return map;
  }, [tableGroups]);
  const allFields = useMemo(() => Array.from(fieldLookup.values()), [fieldLookup]);

  // Active Widget Helper
  const activeWidget = useMemo(() => 
    widgets.find(w => w.id === activeWidgetId) || null, 
  [widgets, activeWidgetId]);

  // -- Effects --
  useEffect(() => {
    if (semanticModelsQuery.data?.length && !selectedModelId) {
      setSelectedModelId(semanticModelsQuery.data[0].id);
    }
  }, [semanticModelsQuery.data, selectedModelId]);

  useEffect(() => {
    // Reset on model change
    setWidgets([]);
    setActiveWidgetId(null);
  }, [selectedModelId]);

  // -- Widget Handlers --

  const handleAddWidget = () => {
    const newWidget: BiWidget = {
      id: Math.random().toString(36).substr(2, 9),
      title: `Analysis ${widgets.length + 1}`,
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
      isLoading: false
    };
    setWidgets([...widgets, newWidget]);
    setActiveWidgetId(newWidget.id);
    setIsConfigOpen(true);
  };

  const handleRemoveWidget = (id: string) => {
    setWidgets(widgets.filter(w => w.id !== id));
    if (activeWidgetId === id) setActiveWidgetId(null);
  };

  const updateWidget = (id: string, updates: Partial<BiWidget>) => {
    setWidgets(current => current.map(w => w.id === id ? { ...w, ...updates } : w));
  };

  // -- Field & Config Handlers --

  const handleAddFieldToWidget = (widgetId: string, field: FieldOption, targetKind?: 'dimension' | 'measure') => {
    const widget = widgets.find(w => w.id === widgetId);
    if (!widget) return;

    let kind = targetKind;
    if (!kind) {
      kind = (field.kind === 'measure' || field.kind === 'metric') ? 'measure' : 'dimension';
    }

    if (kind === 'dimension') {
      if (!widget.dimensions.includes(field.id)) {
        updateWidget(widgetId, { dimensions: [...widget.dimensions, field.id] });
      }
    } else {
      if (!widget.measures.includes(field.id)) {
        updateWidget(widgetId, { measures: [...widget.measures, field.id] });
      }
    }
    setActiveWidgetId(widgetId);
  };

  const handleRemoveFieldFromWidget = (widgetId: string, fieldId: string, kind: 'dimension' | 'measure') => {
    const widget = widgets.find(w => w.id === widgetId);
    if (!widget) return;

    if (kind === 'dimension') {
      updateWidget(widgetId, { dimensions: widget.dimensions.filter(id => id !== fieldId) });
    } else {
      updateWidget(widgetId, { measures: widget.measures.filter(id => id !== fieldId) });
    }
  };

  // Wrapper for Sidebar clicks (adds to active widget or creates new)
  const handleSidebarAddField = (field: FieldOption) => {
    if (activeWidgetId) {
      handleAddFieldToWidget(activeWidgetId, field);
    } else {
      // Create new widget with this field
      const id = Math.random().toString(36).substr(2, 9);
      const kind = (field.kind === 'measure' || field.kind === 'metric') ? 'measure' : 'dimension';
      const newWidget: BiWidget = {
        id,
        title: `Analysis ${widgets.length + 1}`,
        type: 'bar',
        size: 'small',
        measures: kind === 'measure' ? [field.id] : [],
        dimensions: kind === 'dimension' ? [field.id] : [],
        filters: [],
        orderBys: [],
        limit: 500,
        timeDimension: '',
        timeGrain: '',
        timeRangePreset: '',
        chartX: '',
        chartY: '',
        queryResult: null,
        isLoading: false
      };
      setWidgets([...widgets, newWidget]);
      setActiveWidgetId(id);
      setIsConfigOpen(true);
    }
  };

  // -- Query Execution --

  const queryMutation = useMutation<SemanticQueryResponse, Error, { widgetId: string, payload: SemanticQueryRequestPayload }>({ 
    mutationFn: async ({ payload }) => runSemanticQuery(organizationId, payload),
    onMutate: ({ widgetId }) => {
      updateWidget(widgetId, { isLoading: true, error: null });
    },
    onSuccess: (data, { widgetId }) => {
      updateWidget(widgetId, { isLoading: false, queryResult: data });
    },
    onError: (error, { widgetId }) => {
      updateWidget(widgetId, { isLoading: false, error: error.message });
    }
  });

  const handleRunQuery = () => {
    if (!organizationId || !selectedModelId || !activeWidgetId) return;
    const widget = activeWidget;
    if (!widget) return;

    // Construct Payload
    const timeDimensionsPayload = widget.timeDimension ? [{
      dimension: widget.timeDimension,
      granularity: widget.timeGrain || undefined,
      dateRange: widget.timeRangePreset || undefined 
    }] : [];

    const filtersPayload = [...globalFilters, ...widget.filters].map(f => ({
      member: f.member,
      operator: f.operator,
      values: f.values.split(',').map(v => v.trim())
    }));

    const orderPayload = widget.orderBys.length > 0 ? widget.orderBys.map(o => ({
      [o.member]: o.direction
    })) : undefined;

    const payload: SemanticQueryRequestPayload = {
      organizationId,
      projectId: (selectedProjectId === '' ? null : selectedProjectId) ?? null,
      semanticModelId: selectedModelId,
      query: {
        measures: widget.measures,
        dimensions: widget.dimensions,
        timeDimensions: timeDimensionsPayload,
        filters: filtersPayload,
        order: orderPayload,
        limit: widget.limit,
      },
    };

    queryMutation.mutate({ widgetId: activeWidgetId, payload });
  };

  const handleRunAllQueries = () => {
    if (!organizationId || !selectedModelId) return;
    widgets.forEach((widget) => {
      if (widget.dimensions.length === 0 && widget.measures.length === 0) {
        return;
      }
      const timeDimensionsPayload = widget.timeDimension ? [{
        dimension: widget.timeDimension,
        granularity: widget.timeGrain || undefined,
        dateRange: widget.timeRangePreset || undefined 
      }] : [];

      const filtersPayload = [...globalFilters, ...widget.filters].map(f => ({
        member: f.member,
        operator: f.operator,
        values: f.values.split(',').map(v => v.trim())
      }));

      const orderPayload = widget.orderBys.length > 0 ? widget.orderBys.map(o => ({
        [o.member]: o.direction
      })) : undefined;

      const payload: SemanticQueryRequestPayload = {
        organizationId,
        projectId: (selectedProjectId === '' ? null : selectedProjectId) ?? null,
        semanticModelId: selectedModelId,
        query: {
          measures: widget.measures,
          dimensions: widget.dimensions,
          timeDimensions: timeDimensionsPayload,
          filters: filtersPayload,
          order: orderPayload,
          limit: widget.limit,
        },
      };

      queryMutation.mutate({ widgetId: widget.id, payload });
    });
  };

  const handleExportCsv = () => {
    const widget = activeWidget;
    if (!widget?.queryResult?.data?.length) return;
    const columns = Object.keys(widget.queryResult.data[0]);
    const csvContent = [
      columns.join(','),
      ...widget.queryResult.data.map(row => columns.map(c => row[c]).join(','))
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${widget.title.replace(/\s+/g, '_')}_export.csv`;
    link.click();
  };

  if (!organizationId) {
    return <div className="p-10 text-center">Select an organization to continue.</div>;
  }

  const isAnyRunning = widgets.some(widget => widget.isLoading);
  const canRunActive = !!activeWidget && (activeWidget.dimensions.length > 0 || activeWidget.measures.length > 0);
  const canRunAll = widgets.some(widget => widget.dimensions.length > 0 || widget.measures.length > 0);

  return (
    <div className="flex h-[calc(100vh-4rem)] w-full overflow-hidden relative p-4 gap-4">
      {/* Sidebar Island */}
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
      
      {/* Main Canvas Island */}
      <div className="flex-1 flex flex-col rounded-[2.5rem] bg-[color:var(--panel-bg)] border border-[color:var(--panel-border)] shadow-soft overflow-hidden relative">
        <BiHeader 
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
          title={workspaceName}
        />
        
        <BiCanvas 
          widgets={widgets}
          activeWidgetId={activeWidgetId}
          onActivateWidget={(id) => { setActiveWidgetId(id); setIsConfigOpen(true); }}
          onRemoveWidget={handleRemoveWidget}
          onAddWidget={handleAddWidget}
          onAddFieldToWidget={handleAddFieldToWidget}
        />
        
        {/* Config Panel Island */}
        <div className={`absolute top-4 right-4 bottom-4 w-80 z-50 transition-transform duration-300 ease-in-out ${isConfigOpen && activeWidget ? 'translate-x-0' : 'translate-x-[120%]'}`}>
           <div className="h-full rounded-3xl bg-[color:var(--panel-bg)] shadow-soft border border-[color:var(--panel-border)] overflow-hidden">
             {activeWidget && (
               <BiConfigPanel 
                  onClose={() => setIsConfigOpen(false)}
                  // Widget Meta
                  title={activeWidget.title}
                  setTitle={(title) => updateWidget(activeWidget.id, { title })}
                  // Visuals
                  chartX={activeWidget.chartX}
                  setChartX={(x) => updateWidget(activeWidget.id, { chartX: x })}
                  chartY={activeWidget.chartY}
                  setChartY={(y) => updateWidget(activeWidget.id, { chartY: y })}
                  chartType={activeWidget.type}
                  setChartType={(type) => updateWidget(activeWidget.id, { type })}
                  widgetSize={activeWidget.size}
                  setWidgetSize={(size) => updateWidget(activeWidget.id, { size })}
                  // Data
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
                  onShowSql={() => alert("SQL Preview")}
                />
             )}
           </div>
        </div>

        <div className={`absolute top-4 right-4 bottom-4 w-80 z-40 transition-transform duration-300 ease-in-out ${isGlobalConfigOpen ? 'translate-x-0' : 'translate-x-[120%]'}`}>
          <div className="h-full rounded-3xl bg-[color:var(--panel-bg)] shadow-soft border border-[color:var(--panel-border)] overflow-hidden">
            <BiGlobalConfigPanel
              onClose={() => setIsGlobalConfigOpen(false)}
              workspaceName={workspaceName}
              setWorkspaceName={setWorkspaceName}
              fields={allFields}
              globalFilters={globalFilters}
              setGlobalFilters={setGlobalFilters}
            />
          </div>
        </div>
      </div>

      <BiAiInput />
    </div>
  );
}

// --- Helper Functions ---

function buildTableGroups(semanticModel?: SemanticModelPayload): TableGroup[] {
  if (!semanticModel || !semanticModel.tables) {
    return [];
  }

  const groups: TableGroup[] = Object.entries(semanticModel.tables).map(([tableKey, table]) => {
    const dimensions: FieldOption[] = (table.dimensions ?? []).map((dim) => ({
      id: dim.full_path || `${tableKey}.${dim.name}`,
      label: dim.alias || dim.name,
      kind: 'dimension',
      type: dim.type,
      description: dim.description,
      tableKey,
    }));

    const measures: FieldOption[] = (table.measures ?? []).map((meas) => ({
      id: meas.full_path || `${tableKey}.${meas.name}`,
      label: meas.name, 
      kind: 'measure',
      type: meas.type,
      description: meas.description,
      aggregation: meas.aggregation,
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
    const metricGroup: TableGroup = {
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
    };
    groups.push(metricGroup);
  }

  return groups;
}
