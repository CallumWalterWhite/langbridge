import { Copy, Plus, Trash2 } from "lucide-react";

import { PageEmpty, Panel } from "../PagePrimitives";
import { formatValue } from "../../lib/format";
import {
  DASHBOARD_BUILDER_TIME_PRESETS,
  ensureOperatorForField,
  getDefaultFilterOperator,
  getFilterValuePlaceholder,
  isValuelessFilter,
  parseDateRangeFilterValues,
  serializeDateRangeFilterValues,
  usesDateRangePresetInput,
} from "../../lib/dashboardBuilder";
import { DashboardBuilderFieldSelect } from "./DashboardBuilderFieldSelect";

function FilterEditor({
  title,
  filters,
  fields,
  fieldTypesByValue,
  onAdd,
  onPatch,
  onRemove,
}) {
  return (
    <div className="field-group">
      <div className="field-group-header">
        <strong>{title}</strong>
        <button className="ghost-button" type="button" onClick={onAdd}>
          Add filter
        </button>
      </div>

      {filters.length > 0 ? (
        <div className="page-stack">
          {filters.map((filter) => {
            const field = fields.find((item) => item.id === filter.member) || null;
            const operators = (
              field && usesDateRangePresetInput(field, fieldTypesByValue, "indaterange")
                ? [
                    { value: "indaterange", label: "In date range" },
                    { value: "notindaterange", label: "Not in date range" },
                    { value: "set", label: "Is set" },
                    { value: "notset", label: "Is not set" },
                  ]
                : [
                    { value: "equals", label: "Equals" },
                    { value: "notequals", label: "Not equals" },
                    { value: "contains", label: "Contains" },
                    { value: "gt", label: "Greater than" },
                    { value: "gte", label: "Greater or equal" },
                    { value: "lt", label: "Less than" },
                    { value: "lte", label: "Less or equal" },
                    { value: "in", label: "In list" },
                    { value: "notin", label: "Not in list" },
                    { value: "set", label: "Is set" },
                    { value: "notset", label: "Is not set" },
                  ]
            ).map((item) => ({
              ...item,
            }));
            const normalizedOperator = ensureOperatorForField(
              filter.operator,
              field,
              fieldTypesByValue,
            );
            const usesDatePreset = usesDateRangePresetInput(
              field,
              fieldTypesByValue,
              normalizedOperator,
            );
            const dateRangeState = parseDateRangeFilterValues(filter.values);

            return (
              <div key={filter.id} className="field-group">
                <DashboardBuilderFieldSelect
                  fields={fields}
                  value={filter.member}
                  onChange={(value) => {
                    const nextField = fields.find((item) => item.id === value) || null;
                    onPatch(filter.id, {
                      member: value,
                      operator: ensureOperatorForField(
                        filter.operator,
                        nextField,
                        fieldTypesByValue,
                      ),
                    });
                  }}
                  placeholder="Select field"
                />

                <div className="form-grid compact">
                  <label className="field">
                    <span>Operator</span>
                    <select
                      className="select-input"
                      value={normalizedOperator}
                      onChange={(event) =>
                        onPatch(filter.id, {
                          operator: ensureOperatorForField(
                            event.target.value,
                            field,
                            fieldTypesByValue,
                          ),
                        })
                      }
                    >
                      {operators.map((operator) => (
                        <option key={operator.value} value={operator.value}>
                          {operator.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  {usesDatePreset ? (
                    <label className="field">
                      <span>Preset</span>
                      <select
                        className="select-input"
                        value={dateRangeState.preset}
                        onChange={(event) =>
                          onPatch(filter.id, {
                            values: serializeDateRangeFilterValues({
                              ...dateRangeState,
                              preset: event.target.value,
                            }),
                          })
                        }
                      >
                        {DASHBOARD_BUILDER_TIME_PRESETS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : (
                    <label className="field">
                      <span>Value</span>
                      <input
                        className="text-input"
                        type="text"
                        value={filter.values}
                        onChange={(event) => onPatch(filter.id, { values: event.target.value })}
                        placeholder={getFilterValuePlaceholder(
                          field,
                          fieldTypesByValue,
                          normalizedOperator,
                        )}
                        disabled={isValuelessFilter(normalizedOperator)}
                      />
                    </label>
                  )}
                </div>

                {usesDatePreset &&
                (dateRangeState.preset === "custom_between" ||
                  dateRangeState.preset === "custom_before" ||
                  dateRangeState.preset === "custom_after" ||
                  dateRangeState.preset === "custom_on") ? (
                  <div className="form-grid compact">
                    <label className="field">
                      <span>
                        {dateRangeState.preset === "custom_between"
                          ? "From"
                          : "Date"}
                      </span>
                      <input
                        className="text-input"
                        type="date"
                        value={dateRangeState.from}
                        onChange={(event) =>
                          onPatch(filter.id, {
                            values: serializeDateRangeFilterValues({
                              ...dateRangeState,
                              from: event.target.value,
                            }),
                          })
                        }
                      />
                    </label>

                    {dateRangeState.preset === "custom_between" ? (
                      <label className="field">
                        <span>To</span>
                        <input
                          className="text-input"
                          type="date"
                          value={dateRangeState.to}
                          onChange={(event) =>
                            onPatch(filter.id, {
                              values: serializeDateRangeFilterValues({
                                ...dateRangeState,
                                to: event.target.value,
                              }),
                            })
                          }
                        />
                      </label>
                    ) : null}
                  </div>
                ) : null}

                <div className="page-actions">
                  <button
                    className="ghost-button danger-button"
                    type="button"
                    onClick={() => onRemove(filter.id)}
                  >
                    Remove filter
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <PageEmpty title="No filters" message={`Add ${title.toLowerCase()} to constrain widget queries.`} />
      )}
    </div>
  );
}

export function DashboardBuilderSidebar({
  boards,
  activeBoard,
  totalWidgets,
  fieldOptions,
  fieldTypesByValue,
  onSelectBoard,
  onCreateBoard,
  onDuplicateBoard,
  onRemoveBoard,
  onUpdateBoard,
  onAddGlobalFilter,
  onPatchGlobalFilter,
  onRemoveGlobalFilter,
}) {
  return (
    <div className="detail-stack dashboard-builder-sidebar-stack">
      <Panel
        title="Dashboards"
        className="dashboard-builder-sidebar-panel dashboard-builder-compact-panel"
        actions={
          <div className="panel-actions-inline">
            <button className="ghost-button" type="button" onClick={onCreateBoard}>
              <Plus className="button-icon" aria-hidden="true" />
              New
            </button>
            <button className="ghost-button" type="button" onClick={onDuplicateBoard} disabled={!activeBoard}>
              <Copy className="button-icon" aria-hidden="true" />
              Duplicate
            </button>
            <button className="ghost-button" type="button" onClick={onRemoveBoard} disabled={!activeBoard}>
              <Trash2 className="button-icon" aria-hidden="true" />
              Delete
            </button>
          </div>
        }
      >
        <div className="dashboard-builder-panel-meta">
          <span>{formatValue(boards.length)} dashboards</span>
          <span>{formatValue(totalWidgets)} widgets</span>
          <span>{formatValue(activeBoard?.lastRefreshedAt || "Not run yet")}</span>
        </div>
        <div className="board-list dashboard-builder-board-list">
          {boards.map((board) => (
            <button
              key={board.id}
              className={`list-card ${board.id === activeBoard?.id ? "active" : ""}`}
              type="button"
              onClick={() => onSelectBoard(board.id)}
            >
              <div className="dashboard-builder-board-card-top">
                <strong>{board.name}</strong>
                <span className="chip">{board.widgets.length}</span>
              </div>
              <small>{board.selectedModel || "No model selected"}</small>
            </button>
          ))}
        </div>
      </Panel>

      {activeBoard ? (
        <Panel title="Dashboard settings" className="dashboard-builder-sidebar-panel dashboard-builder-compact-panel">
          <div className="page-stack">
            <label className="field">
              <span>Name</span>
              <input
                className="text-input"
                type="text"
                value={activeBoard.name}
                onChange={(event) => onUpdateBoard(activeBoard.id, { name: event.target.value })}
              />
            </label>

            <label className="field">
              <span>Description</span>
              <textarea
                className="textarea-input"
                value={activeBoard.description || ""}
                onChange={(event) =>
                  onUpdateBoard(activeBoard.id, { description: event.target.value })
                }
              />
            </label>

            <FilterEditor
              title="Global filters"
              filters={Array.isArray(activeBoard.globalFilters) ? activeBoard.globalFilters : []}
              fields={fieldOptions}
              fieldTypesByValue={fieldTypesByValue}
              onAdd={onAddGlobalFilter}
              onPatch={onPatchGlobalFilter}
              onRemove={onRemoveGlobalFilter}
            />
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
