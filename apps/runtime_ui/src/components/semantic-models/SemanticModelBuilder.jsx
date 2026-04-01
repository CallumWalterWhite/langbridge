import { useMemo, useState } from "react";

import { PageEmpty } from "../PagePrimitives";
import { getErrorMessage } from "../../lib/format";
import { fetchDataset } from "../../lib/runtimeApi";
import {
  buildSemanticDatasetFromRuntimeDataset,
  buildSemanticModelDefinition,
  buildSemanticModelRequest,
  cloneSemanticModelBuilderState,
  createEmptySemanticDimension,
  createEmptySemanticMeasure,
  createEmptySemanticRelationship,
  SEMANTIC_DIMENSION_TYPES,
  SEMANTIC_MEASURE_AGGREGATIONS,
  SEMANTIC_MEASURE_TYPES,
  SEMANTIC_RELATIONSHIP_TYPES,
  sanitizeSemanticKey,
} from "../../lib/semanticModelBuilder";
import { renderJson } from "../../lib/runtimeUi";

function countFields(semanticDatasets, key) {
  return (Array.isArray(semanticDatasets) ? semanticDatasets : []).reduce(
    (total, dataset) => total + (Array.isArray(dataset?.[key]) ? dataset[key].length : 0),
    0,
  );
}

function SemanticFieldRow({
  field,
  typeOptions,
  showPrimaryKey = false,
  showAggregation = false,
  onPatch,
  onRemove,
}) {
  return (
    <div className="field-group">
      <div className="form-grid compact">
        <label className="field">
          <span>Name</span>
          <input
            className="text-input"
            type="text"
            value={field.name}
            onChange={(event) => onPatch({ name: event.target.value })}
            placeholder="field_name"
          />
        </label>
        <label className="field">
          <span>Expression</span>
          <input
            className="text-input"
            type="text"
            value={field.expression || ""}
            onChange={(event) => onPatch({ expression: event.target.value })}
            placeholder="source_column"
          />
        </label>
        <label className="field">
          <span>Type</span>
          <select
            className="select-input"
            value={field.type}
            onChange={(event) => onPatch({ type: event.target.value })}
          >
            {typeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        {showAggregation ? (
          <label className="field">
            <span>Aggregation</span>
            <select
              className="select-input"
              value={field.aggregation || "sum"}
              onChange={(event) => onPatch({ aggregation: event.target.value })}
            >
              {SEMANTIC_MEASURE_AGGREGATIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      <div className="page-actions">
        {showPrimaryKey ? (
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={Boolean(field.primaryKey)}
              onChange={(event) => onPatch({ primaryKey: event.target.checked })}
            />
            <span>{field.primaryKey ? "Primary key" : "Mark as primary key"}</span>
          </label>
        ) : null}
        <button className="ghost-button danger-button" type="button" onClick={onRemove}>
          Remove
        </button>
      </div>
    </div>
  );
}

function SemanticRelationshipRow({ relationship, datasetOptions, onPatch, onRemove }) {
  const sourceDataset = datasetOptions.find((item) => item.value === relationship.sourceDataset);
  const targetDataset = datasetOptions.find((item) => item.value === relationship.targetDataset);

  return (
    <div className="field-group">
      <div className="form-grid compact">
        <label className="field">
          <span>Name</span>
          <input
            className="text-input"
            type="text"
            value={relationship.name}
            onChange={(event) => onPatch({ name: event.target.value })}
            placeholder="orders_to_customers"
          />
        </label>
        <label className="field">
          <span>Type</span>
          <select
            className="select-input"
            value={relationship.type}
            onChange={(event) => onPatch({ type: event.target.value })}
          >
            {SEMANTIC_RELATIONSHIP_TYPES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Source dataset</span>
          <select
            className="select-input"
            value={relationship.sourceDataset}
            onChange={(event) =>
              onPatch({ sourceDataset: event.target.value, sourceField: "" })
            }
          >
            <option value="">Select dataset</option>
            {datasetOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Source field</span>
          <select
            className="select-input"
            value={relationship.sourceField}
            onChange={(event) => onPatch({ sourceField: event.target.value })}
          >
            <option value="">Select field</option>
            {(sourceDataset?.fields || []).map((fieldName) => (
              <option key={`${relationship.id}-${fieldName}-source`} value={fieldName}>
                {fieldName}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Target dataset</span>
          <select
            className="select-input"
            value={relationship.targetDataset}
            onChange={(event) =>
              onPatch({ targetDataset: event.target.value, targetField: "" })
            }
          >
            <option value="">Select dataset</option>
            {datasetOptions.map((option) => (
              <option key={`${option.value}-target`} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Target field</span>
          <select
            className="select-input"
            value={relationship.targetField}
            onChange={(event) => onPatch({ targetField: event.target.value })}
          >
            <option value="">Select field</option>
            {(targetDataset?.fields || []).map((fieldName) => (
              <option key={`${relationship.id}-${fieldName}-target`} value={fieldName}>
                {fieldName}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="page-actions">
        <small className="field-hint">
          {relationship.sourceDataset &&
          relationship.sourceField &&
          relationship.targetDataset &&
          relationship.targetField
            ? `${relationship.sourceDataset}.${relationship.sourceField} = ${relationship.targetDataset}.${relationship.targetField}`
            : "Select source and target fields to complete the relationship."}
        </small>
        <button className="ghost-button danger-button" type="button" onClick={onRemove}>
          Remove relationship
        </button>
      </div>
    </div>
  );
}

export function SemanticModelBuilder({
  mode = "create",
  initialState,
  datasetOptions,
  submitting = false,
  submitError = "",
  submitLabel,
  onSubmit,
  onCancel,
  onDelete,
  deleteSubmitting = false,
}) {
  const [builderState, setBuilderState] = useState(() =>
    cloneSemanticModelBuilderState(initialState),
  );
  const [datasetSearch, setDatasetSearch] = useState("");
  const [localError, setLocalError] = useState("");
  const [loadingDatasetNames, setLoadingDatasetNames] = useState([]);

  const selectedDatasetNames = useMemo(
    () =>
      new Set(
        (Array.isArray(builderState.semanticDatasets) ? builderState.semanticDatasets : [])
          .map((dataset) => String(dataset?.sourceDatasetName || "").trim())
          .filter(Boolean),
      ),
    [builderState.semanticDatasets],
  );
  const filteredDatasetOptions = useMemo(() => {
    const searchTerm = String(datasetSearch || "").trim().toLowerCase();
    const items = Array.isArray(datasetOptions) ? datasetOptions : [];
    const filtered = !searchTerm
      ? items
      : items.filter((dataset) =>
          [
            dataset?.label,
            dataset?.name,
            dataset?.sql_alias,
            dataset?.connector,
            dataset?.materialization_mode,
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase()
            .includes(searchTerm),
        );
    return [...filtered].sort((left, right) => {
      const selectedDelta =
        Number(selectedDatasetNames.has(String(right?.name || ""))) -
        Number(selectedDatasetNames.has(String(left?.name || "")));
      if (selectedDelta !== 0) {
        return selectedDelta;
      }
      return String(left?.label || left?.name || "").localeCompare(
        String(right?.label || right?.name || ""),
      );
    });
  }, [datasetOptions, datasetSearch, selectedDatasetNames]);
  const dimensionCount = countFields(builderState.semanticDatasets, "dimensions");
  const measureCount = countFields(builderState.semanticDatasets, "measures");
  const previewJson = useMemo(
    () => renderJson(buildSemanticModelDefinition(builderState)),
    [builderState],
  );
  const relationshipDatasetOptions = useMemo(
    () =>
      (Array.isArray(builderState.semanticDatasets) ? builderState.semanticDatasets : []).map(
        (dataset) => ({
          value: dataset.semanticKey,
          label: dataset.semanticKey,
          fields: [
            ...(Array.isArray(dataset.dimensions) ? dataset.dimensions : []),
            ...(Array.isArray(dataset.measures) ? dataset.measures : []),
          ]
            .map((field) => String(field?.name || "").trim())
            .filter(Boolean),
        }),
      ),
    [builderState.semanticDatasets],
  );

  function patchDataset(datasetId, updater) {
    setBuilderState((current) => {
      const currentDataset = (current.semanticDatasets || []).find((dataset) => dataset.id === datasetId);
      if (!currentDataset) {
        return current;
      }
      const nextDataset =
        typeof updater === "function" ? updater(currentDataset) : { ...currentDataset, ...updater };
      const nextState = {
        ...current,
        semanticDatasets: current.semanticDatasets.map((dataset) =>
          dataset.id === datasetId ? nextDataset : dataset,
        ),
      };
      if (currentDataset.semanticKey !== nextDataset.semanticKey) {
        nextState.relationships = (current.relationships || []).map((relationship) => ({
          ...relationship,
          sourceDataset:
            relationship.sourceDataset === currentDataset.semanticKey
              ? nextDataset.semanticKey
              : relationship.sourceDataset,
          targetDataset:
            relationship.targetDataset === currentDataset.semanticKey
              ? nextDataset.semanticKey
              : relationship.targetDataset,
        }));
      }
      return nextState;
    });
  }

  function patchField(datasetId, fieldType, fieldId, updater) {
    patchDataset(datasetId, (dataset) => ({
      ...dataset,
      [fieldType]: dataset[fieldType].map((field) =>
        field.id === fieldId ? { ...field, ...updater } : field,
      ),
    }));
  }

  async function handleToggleDataset(dataset) {
    const datasetName = String(dataset?.name || "").trim();
    if (!datasetName) {
      return;
    }
    setLocalError("");

    if (selectedDatasetNames.has(datasetName)) {
      setBuilderState((current) => {
        const removed = (current.semanticDatasets || []).find(
          (item) => String(item?.sourceDatasetName || "").trim() === datasetName,
        );
        if (!removed) {
          return current;
        }
        return {
          ...current,
          semanticDatasets: current.semanticDatasets.filter(
            (item) => String(item?.sourceDatasetName || "").trim() !== datasetName,
          ),
          relationships: (current.relationships || []).filter(
            (relationship) =>
              relationship.sourceDataset !== removed.semanticKey &&
              relationship.targetDataset !== removed.semanticKey,
          ),
        };
      });
      return;
    }

    setLoadingDatasetNames((current) => [...current, datasetName]);
    try {
      const detail = await fetchDataset(datasetName);
      setBuilderState((current) => ({
        ...current,
        semanticDatasets: [
          ...current.semanticDatasets,
          buildSemanticDatasetFromRuntimeDataset(
            detail,
            current.semanticDatasets.map((item) => item.semanticKey),
          ),
        ],
      }));
    } catch (caughtError) {
      setLocalError(getErrorMessage(caughtError));
    } finally {
      setLoadingDatasetNames((current) => current.filter((item) => item !== datasetName));
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    setLocalError("");
    try {
      onSubmit(buildSemanticModelRequest(builderState));
    } catch (caughtError) {
      setLocalError(getErrorMessage(caughtError));
    }
  }

  return (
    <form className="page-stack" onSubmit={handleSubmit}>
      <div className="form-grid">
        <label className="field">
          <span>Name</span>
          <input
            className="text-input"
            type="text"
            value={builderState.name}
            onChange={(event) =>
              setBuilderState((current) => ({ ...current, name: event.target.value }))
            }
            placeholder="commerce_performance"
            disabled={mode === "edit" || submitting}
          />
          {mode === "edit" ? (
            <small className="field-hint">
              Runtime-managed semantic model names are stable after creation.
            </small>
          ) : null}
        </label>

        <label className="field">
          <span>Description</span>
          <input
            className="text-input"
            type="text"
            value={builderState.description}
            onChange={(event) =>
              setBuilderState((current) => ({ ...current, description: event.target.value }))
            }
            placeholder="Dataset-backed semantic layer"
            disabled={submitting}
          />
        </label>
      </div>

      <div className="inline-notes">
        <span>{builderState.semanticDatasets.length} semantic datasets</span>
        <span>{dimensionCount} dimensions</span>
        <span>{measureCount} measures</span>
        <span>{builderState.relationships.length} relationships</span>
      </div>

      <section className="summary-grid">
        <div className="field-group">
          <div className="field-group-header">
            <strong>Source datasets</strong>
            <span>{filteredDatasetOptions.length} visible</span>
          </div>

          <label className="field">
            <span>Find datasets</span>
            <input
              className="text-input"
              type="search"
              value={datasetSearch}
              onChange={(event) => setDatasetSearch(event.target.value)}
              placeholder="Search datasets by name or connector"
              disabled={submitting}
            />
          </label>

          {filteredDatasetOptions.length > 0 ? (
            <div className="stack-list">
              {filteredDatasetOptions.map((dataset) => {
                const datasetName = String(dataset?.name || "").trim();
                const selected = selectedDatasetNames.has(datasetName);
                const loading = loadingDatasetNames.includes(datasetName);
                return (
                  <div key={dataset.id || datasetName} className="list-card static">
                    <div className="list-card-topline">
                      <strong>{dataset.label || dataset.name}</strong>
                      <span className="tag">{dataset.materialization_mode || "runtime"}</span>
                    </div>
                    <span>
                      {[dataset.connector, dataset.sql_alias].filter(Boolean).join(" | ")}
                    </span>
                    <small>{selected ? "Included in builder" : "Available for inclusion"}</small>
                    <label className="checkbox-field">
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => void handleToggleDataset(dataset)}
                        disabled={submitting || loading}
                      />
                      <span>
                        {loading
                          ? "Loading runtime schema..."
                          : selected
                            ? "Included"
                            : "Include dataset"}
                      </span>
                    </label>
                  </div>
                );
              })}
            </div>
          ) : (
            <PageEmpty
              title="No datasets found"
              message={
                Array.isArray(datasetOptions) && datasetOptions.length > 0
                  ? "Adjust the dataset filter."
                  : "Create at least one dataset before building a semantic model."
              }
            />
          )}
        </div>

        <div className="field-group">
          <div className="field-group-header">
            <strong>Selected datasets</strong>
            <span>{builderState.semanticDatasets.length} bound</span>
          </div>
          {builderState.semanticDatasets.length > 0 ? (
            <div className="detail-card-grid">
              {builderState.semanticDatasets.map((dataset) => (
                <article key={dataset.id} className="detail-card">
                  <strong>{dataset.semanticKey}</strong>
                  <span>{dataset.sourceDatasetLabel || dataset.sourceDatasetName}</span>
                  <div className="tag-list">
                    <span className="tag">{dataset.dimensions.length} dimensions</span>
                    <span className="tag">{dataset.measures.length} measures</span>
                  </div>
                  <small>{dataset.relationName || dataset.sourceDatasetName}</small>
                </article>
              ))}
            </div>
          ) : (
            <PageEmpty
              title="No datasets selected"
              message="Choose one or more runtime datasets to start building the semantic model."
            />
          )}
        </div>
      </section>

      <div className="field-group">
        <div className="field-group-header">
          <strong>Semantic datasets</strong>
          <span>Dimensions, measures, and relation names</span>
        </div>

        {builderState.semanticDatasets.length > 0 ? (
          <div className="page-stack">
            {builderState.semanticDatasets.map((dataset) => (
              <section key={dataset.id} className="field-group">
                <div className="field-group-header">
                  <strong>{dataset.semanticKey}</strong>
                  <span>{dataset.sourceDatasetLabel || dataset.sourceDatasetName}</span>
                </div>

                <div className="form-grid compact">
                  <label className="field">
                    <span>Semantic key</span>
                    <input
                      className="text-input"
                      type="text"
                      value={dataset.semanticKey}
                      onChange={(event) =>
                        patchDataset(dataset.id, (current) => ({
                          ...current,
                          semanticKey:
                            sanitizeSemanticKey(event.target.value) || current.semanticKey,
                        }))
                      }
                      disabled={submitting}
                    />
                  </label>

                  <label className="field">
                    <span>Source dataset</span>
                    <input
                      className="text-input"
                      type="text"
                      value={dataset.sourceDatasetLabel || dataset.sourceDatasetName}
                      disabled
                    />
                  </label>

                  <label className="field">
                    <span>Relation name</span>
                    <input
                      className="text-input"
                      type="text"
                      value={dataset.relationName || ""}
                      onChange={(event) =>
                        patchDataset(dataset.id, { relationName: event.target.value })
                      }
                      disabled={submitting}
                    />
                  </label>

                  <label className="field">
                    <span>Description</span>
                    <input
                      className="text-input"
                      type="text"
                      value={dataset.description || ""}
                      onChange={(event) =>
                        patchDataset(dataset.id, { description: event.target.value })
                      }
                      disabled={submitting}
                    />
                  </label>
                </div>

                <div className="field-section-list">
                  <div className="field-group">
                    <div className="field-group-header">
                      <strong>Dimensions</strong>
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() =>
                          patchDataset(dataset.id, (current) => ({
                            ...current,
                            dimensions: [...current.dimensions, createEmptySemanticDimension()],
                          }))
                        }
                        disabled={submitting}
                      >
                        Add dimension
                      </button>
                    </div>

                    {dataset.dimensions.length > 0 ? (
                      <div className="page-stack">
                        {dataset.dimensions.map((field) => (
                          <SemanticFieldRow
                            key={field.id}
                            field={field}
                            typeOptions={SEMANTIC_DIMENSION_TYPES}
                            showPrimaryKey
                            onPatch={(patch) =>
                              patchField(dataset.id, "dimensions", field.id, patch)
                            }
                            onRemove={() =>
                              patchDataset(dataset.id, (current) => ({
                                ...current,
                                dimensions: current.dimensions.filter((item) => item.id !== field.id),
                              }))
                            }
                          />
                        ))}
                      </div>
                    ) : (
                      <PageEmpty
                        title="No dimensions"
                        message="Add one or more dimensions for this semantic dataset."
                      />
                    )}
                  </div>

                  <div className="field-group">
                    <div className="field-group-header">
                      <strong>Measures</strong>
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() =>
                          patchDataset(dataset.id, (current) => ({
                            ...current,
                            measures: [...current.measures, createEmptySemanticMeasure()],
                          }))
                        }
                        disabled={submitting}
                      >
                        Add measure
                      </button>
                    </div>

                    {dataset.measures.length > 0 ? (
                      <div className="page-stack">
                        {dataset.measures.map((field) => (
                          <SemanticFieldRow
                            key={field.id}
                            field={field}
                            typeOptions={SEMANTIC_MEASURE_TYPES}
                            showAggregation
                            onPatch={(patch) =>
                              patchField(dataset.id, "measures", field.id, patch)
                            }
                            onRemove={() =>
                              patchDataset(dataset.id, (current) => ({
                                ...current,
                                measures: current.measures.filter((item) => item.id !== field.id),
                              }))
                            }
                          />
                        ))}
                      </div>
                    ) : (
                      <PageEmpty
                        title="No measures"
                        message="Add one or more measures for this semantic dataset."
                      />
                    )}
                  </div>
                </div>
              </section>
            ))}
          </div>
        ) : (
          <PageEmpty
            title="No semantic datasets"
            message="Select at least one runtime dataset to configure semantic fields."
          />
        )}
      </div>

      <div className="field-group">
        <div className="field-group-header">
          <strong>Relationships</strong>
          <button
            className="ghost-button"
            type="button"
            onClick={() =>
              setBuilderState((current) => ({
                ...current,
                relationships: [
                  ...current.relationships,
                  createEmptySemanticRelationship(
                    current.semanticDatasets.map((dataset) => dataset.semanticKey),
                  ),
                ],
              }))
            }
            disabled={submitting || builderState.semanticDatasets.length < 2}
          >
            Add relationship
          </button>
        </div>

        {builderState.relationships.length > 0 ? (
          <div className="page-stack">
            {builderState.relationships.map((relationship) => (
              <SemanticRelationshipRow
                key={relationship.id}
                relationship={relationship}
                datasetOptions={relationshipDatasetOptions}
                onPatch={(patch) =>
                  setBuilderState((current) => ({
                    ...current,
                    relationships: current.relationships.map((item) =>
                      item.id === relationship.id ? { ...item, ...patch } : item,
                    ),
                  }))
                }
                onRemove={() =>
                  setBuilderState((current) => ({
                    ...current,
                    relationships: current.relationships.filter(
                      (item) => item.id !== relationship.id,
                    ),
                  }))
                }
              />
            ))}
          </div>
        ) : (
          <PageEmpty
            title="No relationships"
            message="Add relationships when this model needs guided multi-dataset joins."
          />
        )}
      </div>

      <div className="field-group">
        <div className="field-group-header">
          <strong>Model preview</strong>
          <span>Generated from the builder state</span>
        </div>
        <pre className="code-block compact">{previewJson}</pre>
      </div>

      {localError ? <div className="error-banner">{localError}</div> : null}
      {submitError ? <div className="error-banner">{submitError}</div> : null}

      <div className="settings-form-actions">
        <button
          className="primary-button"
          type="submit"
          disabled={submitting || builderState.semanticDatasets.length === 0}
        >
          {submitting ? "Saving..." : submitLabel}
        </button>
        <button className="ghost-button" type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        {typeof onDelete === "function" ? (
          <button
            className="ghost-button danger-button"
            type="button"
            onClick={() => void onDelete()}
            disabled={submitting || deleteSubmitting}
          >
            {deleteSubmitting ? "Deleting..." : "Delete semantic model"}
          </button>
        ) : null}
      </div>
    </form>
  );
}
