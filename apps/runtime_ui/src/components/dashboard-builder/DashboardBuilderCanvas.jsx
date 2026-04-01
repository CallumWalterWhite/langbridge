import { RefreshCw } from "lucide-react";

import { ChartPreview } from "../ChartPreview";
import { ResultTable } from "../ResultTable";
import { PageEmpty, Panel } from "../PagePrimitives";
import { formatValue } from "../../lib/format";
import { getDashboardBuilderPalette } from "../../lib/dashboardBuilder";

export function DashboardBuilderCanvas({
  activeBoard,
  activeWidget,
  selectedModel,
  dashboardBuilderEditMode,
  onSelectWidget,
  onRunWidget,
  onAddWidget,
  getSelectedMembers,
  getPrimarySelectedMember,
  summarizeSelectedMembers,
}) {
  return (
    <Panel
      title="Canvas"
      className="dashboard-builder-canvas-panel dashboard-builder-compact-panel"
      actions={
        <div className="panel-actions-inline">
          <span className="chip">{activeBoard?.name || "No dashboard"}</span>
        </div>
      }
    >
      {activeBoard ? (
        <div className="detail-stack">
          <div className="dashboard-builder-panel-meta dashboard-builder-canvas-meta">
            <span>{formatValue(activeBoard.widgets.length)} widgets</span>
            <span>{selectedModel || "No model selected"}</span>
            <span>{dashboardBuilderEditMode ? "Editable" : "Preview"}</span>
          </div>
          {activeBoard.widgets.length > 0 ? (
            <div className="widget-canvas dashboard-builder-widget-canvas">
              {activeBoard.widgets.map((widget) => (
                <article
                  key={widget.id}
                  className={`widget-tile dashboard-builder-widget-tile widget-size-${widget.size} ${widget.id === activeWidget?.id ? "active" : ""}`}
                >
                  <div className="dashboard-builder-widget-head">
                    <button
                      className="widget-tile-header"
                      type="button"
                      onClick={() => onSelectWidget(widget.id)}
                    >
                      <div className="dashboard-builder-widget-title-block">
                        <strong>{widget.title}</strong>
                        <div className="dashboard-builder-widget-metrics">
                          <span className="chart-kind">{widget.chartType}</span>
                          {getSelectedMembers(widget.dimensions).length > 0 ? (
                            <span className="chip">
                              {summarizeSelectedMembers(widget.dimensions, "D")}
                            </span>
                          ) : null}
                          {getSelectedMembers(widget.measures).length > 0 ? (
                            <span className="chip">
                              {summarizeSelectedMembers(widget.measures, "M")}
                            </span>
                          ) : null}
                          {widget.timeDimension ? (
                            <span className="chip">{widget.timeGrain || "raw time"}</span>
                          ) : null}
                        </div>
                      </div>
                    </button>
                    <button
                      className="ghost-button dashboard-builder-widget-run-button"
                      type="button"
                      onClick={() => void onRunWidget(widget)}
                      disabled={!selectedModel || getSelectedMembers(widget.measures).length === 0}
                    >
                      <RefreshCw className="button-icon" aria-hidden="true" />
                      Run
                    </button>
                  </div>
                  {widget.error ? <div className="error-banner">{widget.error}</div> : null}
                  {widget.running ? (
                    <div className="empty-box">Running semantic query...</div>
                  ) : widget.result ? (
                    <div className="detail-stack">
                      <ChartPreview
                        title={widget.title}
                        result={widget.result}
                        metadata={Array.isArray(widget.result?.metadata) ? widget.result.metadata : []}
                        visualization={{
                          chartType: widget.chartType,
                          x: widget.chartX || getPrimarySelectedMember(widget.dimensions),
                          y: widget.chartY
                            ? [widget.chartY]
                            : getSelectedMembers(widget.measures),
                        }}
                        preferredDimension={getPrimarySelectedMember(widget.dimensions)}
                        preferredMeasure={getPrimarySelectedMember(widget.measures)}
                        themeColors={getDashboardBuilderPalette(widget.visualConfig?.paletteId).colors}
                      />
                      {widget.id === activeWidget?.id || widget.chartType === "table" ? (
                        <ResultTable result={widget.result} maxPreviewRows={6} />
                      ) : null}
                    </div>
                  ) : (
                    <PageEmpty title="No result" message="Pick fields and run the widget." />
                  )}
                  <div className="dashboard-builder-widget-foot">
                    <span>{formatValue(widget.result?.rowCount || 0)} rows</span>
                    <span>{formatValue(widget.lastRunAt || "Not run yet")}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <PageEmpty
              title="No widgets yet"
              message="Add a widget to begin composing a runtime dashboard."
              action={
                <button
                  className="primary-button"
                  type="button"
                  onClick={onAddWidget}
                  disabled={!dashboardBuilderEditMode}
                >
                  Add widget
                </button>
              }
            />
          )}
        </div>
      ) : (
        <PageEmpty title="No dashboard selected" message="Create or select a dashboard to continue." />
      )}
    </Panel>
  );
}
