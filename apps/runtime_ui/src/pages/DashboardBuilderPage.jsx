import { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Download,
  Edit3,
  Plus,
  RefreshCw,
} from "lucide-react";

import { DashboardBuilderCanvas } from "../components/dashboard-builder/DashboardBuilderCanvas";
import { DashboardBuilderSidebar } from "../components/dashboard-builder/DashboardBuilderSidebar";
import { DashboardBuilderFieldLibrary } from "../components/dashboard-builder/DashboardBuilderFieldLibrary";
import { DashboardBuilderWidgetInspector } from "../components/dashboard-builder/DashboardBuilderWidgetInspector";
import { readStoredJson } from "../hooks/usePersistentState";
import { useAsyncData } from "../hooks/useAsyncData";
import { fetchSemanticModel, fetchSemanticModels, querySemantic } from "../lib/runtimeApi";
import { formatValue, getErrorMessage } from "../lib/format";
import {
  buildDashboardBuilderQueryPayload,
  createFilterDraft,
  createDashboardBuilderBoard,
  createDashboardBuilderWidget,
  enrichDashboardBuilderResult,
  getDefaultFilterOperator,
  isDateLikeField,
  loadDashboardBuilderState,
} from "../lib/dashboardBuilder";
import {
  copyTextToClipboard,
  DASHBOARD_BUILDER_STORAGE_KEY,
  downloadTextFile,
  extractSemanticDatasets,
  extractSemanticFields,
  renderJson,
  toCsvText,
} from "../lib/runtimeUi";

function getSelectedMembers(values) {
  return Array.isArray(values)
    ? values.filter((value) => String(value || "").trim())
    : [];
}

function getPrimarySelectedMember(values) {
  return getSelectedMembers(values)[0] || "";
}

function toggleSelectedMember(values, nextValue) {
  const normalized = getSelectedMembers(values);
  const value = String(nextValue || "").trim();
  if (!value) {
    return normalized;
  }
  return normalized.includes(value)
    ? normalized.filter((item) => item !== value)
    : [...normalized, value];
}

function formatSemanticMember(value) {
  const parts = String(value || "")
    .split(".")
    .filter(Boolean);
  return parts[parts.length - 1] || String(value || "");
}

function summarizeSelectedMembers(values, prefix) {
  const selected = getSelectedMembers(values).map((value) => formatSemanticMember(value));
  if (selected.length === 0) {
    return "";
  }
  if (selected.length === 1) {
    return `${prefix}: ${selected[0]}`;
  }
  return `${prefix}: ${selected[0]} +${selected.length - 1}`;
}

export function DashboardBuilderPage() {
  const modelsState = useAsyncData(fetchSemanticModels);
  const models = Array.isArray(modelsState.data?.items) ? modelsState.data.items : [];
  const [studioState, setStudioState] = useState(() => loadDashboardBuilderState(readStoredJson));
  const [activeWidgetId, setActiveWidgetId] = useState("");
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [fieldSearch, setFieldSearch] = useState("");
  const [studioNotice, setStudioNotice] = useState("");
  const [dashboardBuilderEditMode, setDashboardBuilderEditMode] = useState(true);
  const deferredFieldSearch = useDeferredValue(fieldSearch);

  const boards = studioState.boards;
  const defaultModelName = models.find((item) => item.default)?.name || models[0]?.name || "";
  const activeBoard =
    boards.find((board) => board.id === studioState.activeBoardId) || boards[0] || null;
  const activeWidget =
    activeBoard?.widgets.find((widget) => widget.id === activeWidgetId) ||
    activeBoard?.widgets[0] ||
    null;
  const selectedModel = activeBoard?.selectedModel || "";
  const fields = extractSemanticFields(detail);
  const semanticDatasets = extractSemanticDatasets(detail);
  const fieldTypesByValue = useMemo(
    () =>
      Object.fromEntries(fields.dimensions.map((field) => [field.value, field.type || "dimension"])),
    [fields.dimensions],
  );
  const fieldOptions = useMemo(
    () => [
      ...fields.dimensions.map((field) => ({
        id: field.value,
        value: field.value,
        label: field.label,
        tableKey: String(field.value || "").split(".")[0] || "",
        type: field.type || "dimension",
        kind: "dimension",
      })),
      ...fields.measures.map((field) => ({
        id: field.value,
        value: field.value,
        label: field.label,
        tableKey: String(field.value || "").split(".")[0] || "",
        type: field.type || "measure",
        aggregation: field.aggregation || null,
        kind: "measure",
      })),
    ],
    [fields.dimensions, fields.measures],
  );
  const dimensionFieldOptions = useMemo(
    () => fieldOptions.filter((field) => field.kind === "dimension"),
    [fieldOptions],
  );
  const measureFieldOptions = useMemo(
    () => fieldOptions.filter((field) => field.kind === "measure"),
    [fieldOptions],
  );
  const activeWidgetDimensions = getSelectedMembers(activeWidget?.dimensions);
  const activeWidgetMeasures = getSelectedMembers(activeWidget?.measures);
  const dateDimensionOptions = dimensionFieldOptions.filter((item) =>
    isDateLikeField(item, fieldTypesByValue),
  );
  const runnableCount =
    activeBoard?.widgets.filter((widget) => getSelectedMembers(widget.measures).length > 0).length || 0;
  const totalWidgets = boards.reduce((count, board) => count + board.widgets.length, 0);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const snapshot = {
      activeBoardId: studioState.activeBoardId,
      boards: studioState.boards.map((board) => ({
        ...board,
        widgets: board.widgets.map(({ result, running, error, ...widget }) => widget),
      })),
    };
    window.localStorage.setItem(DASHBOARD_BUILDER_STORAGE_KEY, JSON.stringify(snapshot));
  }, [studioState]);

  useEffect(() => {
    if (boards.length === 0) {
      const board = createDashboardBuilderBoard({ selectedModel: defaultModelName });
      setStudioState({ boards: [board], activeBoardId: board.id });
      setActiveWidgetId(board.widgets[0]?.id || "");
      return;
    }
    if (!boards.some((board) => board.id === studioState.activeBoardId)) {
      setStudioState((current) => ({ ...current, activeBoardId: current.boards[0]?.id || "" }));
    }
  }, [boards, defaultModelName, studioState.activeBoardId]);

  useEffect(() => {
    if (!activeBoard) {
      setActiveWidgetId("");
      return;
    }
    if (!activeBoard.selectedModel || !models.some((item) => item.name === activeBoard.selectedModel)) {
      updateBoard(activeBoard.id, { selectedModel: defaultModelName });
    }
    if (activeBoard.widgets.length === 0) {
      setActiveWidgetId("");
      return;
    }
    if (!activeBoard.widgets.some((widget) => widget.id === activeWidgetId)) {
      setActiveWidgetId(activeBoard.widgets[0].id);
    }
  }, [activeBoard, activeWidgetId, defaultModelName, models]);

  useEffect(() => {
    let cancelled = false;

    async function loadModelDetail() {
      if (!selectedModel) {
        setDetail(null);
        setDetailError("");
        setDetailLoading(false);
        return;
      }
      setDetailLoading(true);
      setDetailError("");
      try {
        const payload = await fetchSemanticModel(selectedModel);
        if (!cancelled) {
          setDetail(payload);
        }
      } catch (caughtError) {
        if (!cancelled) {
          setDetail(null);
          setDetailError(getErrorMessage(caughtError));
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    }

    void loadModelDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedModel]);

  const filteredSemanticDatasets = semanticDatasets
    .map((dataset) => {
      const search = String(deferredFieldSearch || "").trim().toLowerCase();
      if (!search) {
        return dataset;
      }
      return {
        ...dataset,
        dimensions: dataset.dimensions.filter((item) =>
          String(item?.name || "").toLowerCase().includes(search),
        ),
        measures: dataset.measures.filter((item) =>
          String(item?.name || "").toLowerCase().includes(search),
        ),
      };
    })
    .filter(
      (dataset) =>
        !deferredFieldSearch ||
        String(dataset.name).toLowerCase().includes(String(deferredFieldSearch).toLowerCase()) ||
        dataset.dimensions.length > 0 ||
        dataset.measures.length > 0,
    );

  function updateBoard(boardId, updates) {
    setStudioState((current) => ({
      ...current,
      boards: current.boards.map((board) => (board.id === boardId ? { ...board, ...updates } : board)),
    }));
  }

  function updateWidget(boardId, widgetId, updates) {
    setStudioState((current) => ({
      ...current,
      boards: current.boards.map((board) =>
        board.id === boardId
          ? {
              ...board,
              widgets: board.widgets.map((widget) =>
                widget.id === widgetId ? { ...widget, ...updates } : widget,
              ),
            }
          : board,
      ),
    }));
  }

  function addGlobalFilter() {
    if (!activeBoard) {
      return;
    }
    updateBoard(activeBoard.id, {
      globalFilters: [
        ...(Array.isArray(activeBoard.globalFilters) ? activeBoard.globalFilters : []),
        createFilterDraft({
          member: fieldOptions[0]?.id || "",
          operator: getDefaultFilterOperator(fieldOptions[0], fieldTypesByValue),
        }),
      ],
    });
  }

  function patchGlobalFilter(filterId, updates) {
    if (!activeBoard) {
      return;
    }
    updateBoard(activeBoard.id, {
      globalFilters: (Array.isArray(activeBoard.globalFilters) ? activeBoard.globalFilters : []).map(
        (filter) => (filter.id === filterId ? { ...filter, ...updates } : filter),
      ),
    });
  }

  function removeGlobalFilter(filterId) {
    if (!activeBoard) {
      return;
    }
    updateBoard(activeBoard.id, {
      globalFilters: (Array.isArray(activeBoard.globalFilters) ? activeBoard.globalFilters : []).filter(
        (filter) => filter.id !== filterId,
      ),
    });
  }

  function createBoard() {
    const board = createDashboardBuilderBoard({
      name: `Runtime dashboard ${boards.length + 1}`,
      selectedModel: selectedModel || defaultModelName,
    });
    setStudioState((current) => ({ boards: [board, ...current.boards], activeBoardId: board.id }));
    setActiveWidgetId(board.widgets[0]?.id || "");
    setStudioNotice("Created a local dashboard draft.");
  }

  function removeBoard() {
    if (!activeBoard) {
      return;
    }
    const remaining = boards.filter((board) => board.id !== activeBoard.id);
    if (remaining.length === 0) {
      const freshBoard = createDashboardBuilderBoard({ selectedModel: defaultModelName });
      setStudioState({ boards: [freshBoard], activeBoardId: freshBoard.id });
      setActiveWidgetId(freshBoard.widgets[0]?.id || "");
      setStudioNotice("Reset the Dashboard Builder to a fresh local dashboard.");
      return;
    }
    setStudioState({ boards: remaining, activeBoardId: remaining[0].id });
    setActiveWidgetId(remaining[0].widgets[0]?.id || "");
    setStudioNotice("Removed the selected dashboard.");
  }

  function duplicateBoard() {
    if (!activeBoard) {
      return;
    }
    const board = createDashboardBuilderBoard({
      name: `${activeBoard.name} copy`,
      description: activeBoard.description,
      selectedModel: activeBoard.selectedModel,
      lastRefreshedAt: activeBoard.lastRefreshedAt,
      widgets: activeBoard.widgets.map((widget) => ({
        ...widget,
        id: `widget-${Math.random().toString(36).slice(2, 10)}`,
      })),
    });
    setStudioState((current) => ({ boards: [board, ...current.boards], activeBoardId: board.id }));
    setActiveWidgetId(board.widgets[0]?.id || "");
    setStudioNotice("Duplicated the active dashboard into a new local draft.");
  }

  function addWidget() {
    if (!activeBoard) {
      return;
    }
    const widget = createDashboardBuilderWidget({
      title: `Widget ${activeBoard.widgets.length + 1}`,
      description: "Local runtime widget powered by semantic query execution.",
      dimensions:
        activeWidgetDimensions.length > 0
          ? activeWidgetDimensions
          : fields.dimensions[0]?.value
            ? [fields.dimensions[0].value]
            : [],
      measures:
        activeWidgetMeasures.length > 0
          ? activeWidgetMeasures
          : fields.measures[0]?.value
            ? [fields.measures[0].value]
            : [],
      timeDimension: activeWidget?.timeDimension || dateDimensionOptions[0]?.value || "",
    });
    updateBoard(activeBoard.id, { widgets: [...activeBoard.widgets, widget] });
    setActiveWidgetId(widget.id);
    setStudioNotice("Added a widget to the dashboard canvas.");
  }

  function removeWidget() {
    if (!activeBoard || !activeWidget) {
      return;
    }
    const remainingWidgets = activeBoard.widgets.filter((widget) => widget.id !== activeWidget.id);
    updateBoard(activeBoard.id, { widgets: remainingWidgets });
    setActiveWidgetId(remainingWidgets[0]?.id || "");
    setStudioNotice("Removed the active widget.");
  }

  function assignField(value, kind) {
    if (!activeBoard) {
      return;
    }
    const memberKey = kind === "dimension" ? "dimensions" : "measures";
    const target = activeWidget || activeBoard.widgets[0];
    if (!target) {
      const widget = createDashboardBuilderWidget({
        title: "Widget 1",
        description: "Created from the semantic field library.",
        dimensions:
          kind === "dimension"
            ? [value]
            : fields.dimensions[0]?.value
              ? [fields.dimensions[0].value]
              : [],
        measures:
          kind === "measure"
            ? [value]
            : fields.measures[0]?.value
              ? [fields.measures[0].value]
              : [],
      });
      updateBoard(activeBoard.id, { widgets: [...activeBoard.widgets, widget] });
      setActiveWidgetId(widget.id);
      setStudioNotice(`Created a widget from the selected ${kind}.`);
      return;
    }
    setActiveWidgetId(target.id);
    const currentSelection = getSelectedMembers(target[memberKey]);
    const isAssigned = currentSelection.includes(value);
    updateWidget(activeBoard.id, target.id, {
      [memberKey]: toggleSelectedMember(currentSelection, value),
    });
    setStudioNotice(`${isAssigned ? "Removed" : "Added"} ${kind} ${isAssigned ? "from" : "to"} ${target.title}.`);
  }

  async function runWidget(widget) {
    if (!activeBoard || !selectedModel || getSelectedMembers(widget?.measures).length === 0) {
      return;
    }
    updateWidget(activeBoard.id, widget.id, { running: true, error: "" });
    try {
      const response = await querySemantic(buildDashboardBuilderQueryPayload(activeBoard, widget));
      updateWidget(activeBoard.id, widget.id, {
        running: false,
        error: "",
        lastRunAt: new Date().toISOString(),
        result: enrichDashboardBuilderResult(response),
      });
      updateBoard(activeBoard.id, { lastRefreshedAt: new Date().toISOString() });
    } catch (caughtError) {
      updateWidget(activeBoard.id, widget.id, {
        running: false,
        result: null,
        error: getErrorMessage(caughtError),
      });
    }
  }

  async function runAllWidgets() {
    const widgets =
      activeBoard?.widgets.filter((widget) => getSelectedMembers(widget.measures).length > 0) || [];
    if (widgets.length === 0) {
      setStudioNotice("Add a measure to at least one widget before refreshing the dashboard.");
      return;
    }
    await Promise.all(widgets.map((widget) => runWidget(widget)));
    setStudioNotice("Refreshed all runnable widgets against the local runtime.");
  }

  async function copyGeneratedSql() {
    if (!activeWidget?.result?.generated_sql) {
      return;
    }
    try {
      await copyTextToClipboard(activeWidget.result.generated_sql);
      setStudioNotice("Copied generated SQL to the clipboard.");
    } catch (caughtError) {
      setStudioNotice(getErrorMessage(caughtError));
    }
  }

  function exportWidget() {
    if (!activeWidget?.result) {
      return;
    }
    downloadTextFile(
      `${activeWidget.title.toLowerCase().replaceAll(/\s+/g, "-") || "runtime-widget"}.csv`,
      toCsvText(activeWidget.result),
      "text/csv;charset=utf-8",
    );
    setStudioNotice("Downloaded the active widget as CSV.");
  }

  function exportBoard() {
    if (!activeBoard) {
      return;
    }
    downloadTextFile(
      `${activeBoard.name.toLowerCase().replaceAll(/\s+/g, "-") || "runtime-dashboard"}.json`,
      renderJson({
        exported_at: new Date().toISOString(),
        dashboard: activeBoard,
      }),
      "application/json;charset=utf-8",
    );
    setStudioNotice("Exported the active dashboard as local JSON.");
  }

  return (
    <div className="page-stack dashboard-builder-shell">
      <section className="surface-panel dashboard-builder-command-bar">
        <div className="dashboard-builder-command-bar-main">
          <div className="dashboard-builder-command-bar-copy">
            <p className="eyebrow">Dashboard Builder</p>
            <h2>{activeBoard?.name || "Runtime dashboard"}</h2>
            <div className="dashboard-builder-command-bar-meta">
              <span className="chip">{selectedModel || "No model"}</span>
              <span className="chip">{formatValue(activeBoard?.widgets.length || 0)} widgets</span>
              <span className="chip">{formatValue(runnableCount)} runnable</span>
              <span className={`chip dashboard-builder-mode-chip ${dashboardBuilderEditMode ? "active" : ""}`.trim()}>
                {dashboardBuilderEditMode ? "Edit" : "View"}
              </span>
            </div>
          </div>

          <div className="dashboard-builder-command-bar-controls">
            <label className="field dashboard-builder-compact-field">
              <span>Dashboard</span>
              <select
                className="select-input dashboard-builder-dashboard-select"
                value={activeBoard?.id || ""}
                onChange={(event) =>
                  setStudioState((current) => ({ ...current, activeBoardId: event.target.value }))
                }
              >
                {boards.map((board) => (
                  <option key={board.id} value={board.id}>
                    {board.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field dashboard-builder-compact-field">
              <span>Model</span>
              <select
                className="select-input dashboard-builder-dashboard-select"
                value={selectedModel}
                onChange={(event) =>
                  activeBoard
                    ? updateBoard(activeBoard.id, {
                        selectedModel: event.target.value,
                        lastRefreshedAt: null,
                      })
                    : null
                }
                disabled={!activeBoard || !dashboardBuilderEditMode}
              >
                {models.map((item) => (
                  <option key={item.id || item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="dashboard-builder-command-bar-actions">
          <button
            className={`ghost-button dashboard-builder-mode-toggle ${dashboardBuilderEditMode ? "active" : ""}`}
            type="button"
            onClick={() => setDashboardBuilderEditMode((current) => !current)}
          >
            {dashboardBuilderEditMode ? <Edit3 className="button-icon" aria-hidden="true" /> : <Activity className="button-icon" aria-hidden="true" />}
            {dashboardBuilderEditMode ? "Edit" : "View"}
          </button>
          <button className="primary-button" type="button" onClick={addWidget} disabled={!activeBoard || !dashboardBuilderEditMode}>
            <Plus className="button-icon" aria-hidden="true" />
            Add widget
          </button>
          <button
            className="ghost-button"
            type="button"
            onClick={() => (activeWidget ? void runWidget(activeWidget) : undefined)}
            disabled={!activeWidget || !selectedModel || activeWidgetMeasures.length === 0}
          >
            <Activity className="button-icon" aria-hidden="true" />
            Run active
          </button>
          <button
            className="ghost-button"
            type="button"
            onClick={() => void runAllWidgets()}
            disabled={!activeBoard || !selectedModel || runnableCount === 0}
          >
            <RefreshCw className="button-icon" aria-hidden="true" />
            Run all
          </button>
          <button className="ghost-button" type="button" onClick={exportBoard} disabled={!activeBoard}>
            <Download className="button-icon" aria-hidden="true" />
            Export
          </button>
        </div>
      </section>

      {studioNotice ? <div className="callout dashboard-builder-studio-notice dashboard-builder-status-strip"><span>{studioNotice}</span></div> : null}

      <section className="dashboard-builder-studio-grid dashboard-builder-cloud-grid">
        <div className="detail-stack dashboard-builder-sidebar-stack">
          <DashboardBuilderSidebar
            boards={boards}
            activeBoard={activeBoard}
            totalWidgets={totalWidgets}
            fieldOptions={fieldOptions}
            fieldTypesByValue={fieldTypesByValue}
            onSelectBoard={(boardId) =>
              setStudioState((current) => ({ ...current, activeBoardId: boardId }))
            }
            onCreateBoard={createBoard}
            onDuplicateBoard={duplicateBoard}
            onRemoveBoard={removeBoard}
            onUpdateBoard={updateBoard}
            onAddGlobalFilter={addGlobalFilter}
            onPatchGlobalFilter={patchGlobalFilter}
            onRemoveGlobalFilter={removeGlobalFilter}
          />

          <DashboardBuilderFieldLibrary
            semanticDatasets={filteredSemanticDatasets}
            fields={fields}
            fieldSearch={fieldSearch}
            onFieldSearchChange={setFieldSearch}
            activeWidgetDimensions={activeWidgetDimensions}
            activeWidgetMeasures={activeWidgetMeasures}
            dashboardBuilderEditMode={dashboardBuilderEditMode}
            onAssignField={assignField}
            detailError={detailError}
            detailLoading={detailLoading}
          />
        </div>

        <DashboardBuilderCanvas
          activeBoard={activeBoard}
          activeWidget={activeWidget}
          selectedModel={selectedModel}
          dashboardBuilderEditMode={dashboardBuilderEditMode}
          onSelectWidget={setActiveWidgetId}
          onRunWidget={runWidget}
          onAddWidget={addWidget}
          getSelectedMembers={getSelectedMembers}
          getPrimarySelectedMember={getPrimarySelectedMember}
          summarizeSelectedMembers={summarizeSelectedMembers}
        />

        <DashboardBuilderWidgetInspector
          activeBoard={activeBoard}
          activeWidget={activeWidget}
          selectedModel={selectedModel}
          activeWidgetDimensions={activeWidgetDimensions}
          activeWidgetMeasures={activeWidgetMeasures}
          dashboardBuilderEditMode={dashboardBuilderEditMode}
          fieldOptions={fieldOptions}
          dimensionFieldOptions={dimensionFieldOptions}
          measureFieldOptions={measureFieldOptions}
          dateDimensionOptions={dateDimensionOptions}
          fieldTypesByValue={fieldTypesByValue}
          formatSemanticMember={formatSemanticMember}
          onUpdateWidget={updateWidget}
          onRunWidget={runWidget}
          onRemoveWidget={removeWidget}
          onAssignField={assignField}
          onExportWidget={exportWidget}
          onCopyGeneratedSql={copyGeneratedSql}
        />
      </section>
    </div>
  );
}
