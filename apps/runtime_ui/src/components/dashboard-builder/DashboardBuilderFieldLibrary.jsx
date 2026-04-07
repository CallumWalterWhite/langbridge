import { PageEmpty, Panel } from "../PagePrimitives";
import { formatValue } from "../../lib/format";

export function DashboardBuilderFieldLibrary({
  semanticDatasets,
  fields,
  fieldSearch,
  onFieldSearchChange,
  activeWidgetDimensions,
  activeWidgetMeasures,
  dashboardBuilderEditMode,
  onAssignField,
  detailError,
  detailLoading,
}) {
  return (
    <Panel title="Fields" className="dashboard-builder-sidebar-panel dashboard-builder-compact-panel">
      <div className="dashboard-builder-panel-meta">
        <span>{formatValue(semanticDatasets.length)} datasets</span>
        <span>{formatValue(fields.dimensions.length)} dimensions</span>
        <span>{formatValue(fields.measures.length)} measures</span>
      </div>
      <label className="field">
        <input
          className="text-input"
          type="search"
          value={fieldSearch}
          onChange={(event) => onFieldSearchChange(event.target.value)}
          placeholder="Find field"
        />
      </label>
      {detailError ? <div className="error-banner">{detailError}</div> : null}
      {detailLoading ? (
        <div className="empty-box">Loading semantic model...</div>
      ) : semanticDatasets.length > 0 ? (
        <div className="field-section-list">
          {semanticDatasets.map((dataset) => (
            <div key={dataset.name} className="field-group dashboard-builder-field-group">
              <div className="field-group-header">
                <strong>{dataset.name}</strong>
                <span>
                  {dataset.dimensions.length}D / {dataset.measures.length}M
                </span>
              </div>
              <div className="field-pill-list">
                {dataset.dimensions.map((item) => {
                  const value = `${dataset.name}.${item.name}`;
                  return (
                    <button
                      key={value}
                      className={`field-pill ${activeWidgetDimensions.includes(value) ? "active" : ""} ${!dashboardBuilderEditMode ? "static" : ""}`}
                      type="button"
                      onClick={() => onAssignField(value, "dimension")}
                      disabled={!dashboardBuilderEditMode}
                    >
                      {item.name}
                    </button>
                  );
                })}
                {dataset.measures.map((item) => {
                  const value = `${dataset.name}.${item.name}`;
                  return (
                    <button
                      key={value}
                      className={`field-pill ${activeWidgetMeasures.includes(value) ? "active" : ""} ${!dashboardBuilderEditMode ? "static" : ""}`}
                      type="button"
                      onClick={() => onAssignField(value, "measure")}
                      disabled={!dashboardBuilderEditMode}
                    >
                      {item.name}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <PageEmpty
          title="No fields found"
          message="Adjust the search or select a semantic model with exposed fields."
        />
      )}
    </Panel>
  );
}
