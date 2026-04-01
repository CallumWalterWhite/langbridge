import { useDeferredValue, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  DetailList,
  ManagementBadge,
  ManagementModeNotice,
  PageEmpty,
  Panel,
  SectionTabs,
} from "../components/PagePrimitives";
import { SemanticModelBuilder } from "../components/semantic-models/SemanticModelBuilder";
import { useAsyncData } from "../hooks/useAsyncData";
import {
  createSemanticModel,
  deleteSemanticModel,
  fetchDatasets,
  fetchSemanticModel,
  fetchSemanticModels,
  updateSemanticModel,
} from "../lib/runtimeApi";
import { formatList, formatValue, getErrorMessage } from "../lib/format";
import { describeManagementMode } from "../lib/managedResources";
import { buildSemanticModelBuilderState } from "../lib/semanticModelBuilder";
import {
  buildItemRef,
  extractSemanticDatasets,
  extractSemanticFields,
  renderJson,
  resolveItemByRef,
} from "../lib/runtimeUi";

export function SemanticModelsPage() {
  const params = useParams();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [fieldSearch, setFieldSearch] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const deferredSearch = useDeferredValue(search);
  const deferredFieldSearch = useDeferredValue(fieldSearch);
  const { data, loading, error, reload, setData } = useAsyncData(fetchSemanticModels);
  const { data: datasetPayload } = useAsyncData(fetchDatasets);
  const models = Array.isArray(data?.items) ? data.items : [];
  const datasets = Array.isArray(datasetPayload?.items) ? datasetPayload.items : [];
  const selected = resolveItemByRef(models, params.id);
  const filteredModels = models.filter((item) => {
    const haystack = [
      item.name,
      item.description,
      item.management_mode,
      ...(Array.isArray(item.dataset_names) ? item.dataset_names : []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(String(deferredSearch || "").trim().toLowerCase());
  });

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const semanticDatasets = extractSemanticDatasets(detail);
  const semanticFields = extractSemanticFields(detail);
  const filteredSemanticDatasets = semanticDatasets
    .map((dataset) => {
      const searchTerm = String(deferredFieldSearch || "").trim().toLowerCase();
      if (!searchTerm) {
        return dataset;
      }
      return {
        ...dataset,
        dimensions: dataset.dimensions.filter((item) =>
          String(item?.name || "").toLowerCase().includes(searchTerm),
        ),
        measures: dataset.measures.filter((item) =>
          String(item?.name || "").toLowerCase().includes(searchTerm),
        ),
      };
    })
      .filter(
        (dataset) =>
          !deferredFieldSearch ||
        String(dataset.name)
          .toLowerCase()
          .includes(String(deferredFieldSearch).toLowerCase()) ||
        dataset.dimensions.length > 0 ||
        dataset.measures.length > 0,
    );

  function resetCreateForm() {
    setCreateResetKey((current) => current + 1);
    setCreateError("");
  }

  async function handleCreateSemanticModel(payload) {
    setCreateSubmitting(true);
    setCreateError("");
    setCreateSuccess("");

    try {
      const normalizedPayload = {
        name: payload.name,
        datasets: payload.datasets,
        model: payload.model,
      };
      if (payload.description) {
        normalizedPayload.description = payload.description;
      }

      const created = await createSemanticModel(normalizedPayload);
      setData((current) => {
        const items = Array.isArray(current?.items) ? current.items : [];
        const nextItems = [
          created,
          ...items.filter(
            (item) => String(item?.id || item?.name) !== String(created?.id || created?.name),
          ),
        ];
        return {
          items: nextItems,
          total: nextItems.length,
        };
      });
      setDetail(created);
      setCreateSuccess(`${created.name} is available as a runtime_managed semantic model.`);
      setShowCreate(false);
      resetCreateForm();
      navigate(`/semantic-models/${buildItemRef(created)}`);
      void reload();
    } catch (caughtError) {
      setCreateError(getErrorMessage(caughtError));
    } finally {
      setCreateSubmitting(false);
    }
  }

  const [showCreate, setShowCreate] = useState(false);
  const [createResetKey, setCreateResetKey] = useState(0);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");
  const [showEdit, setShowEdit] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState("");
  const [editSuccess, setEditSuccess] = useState("");
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const editBuilderState = buildSemanticModelBuilderState(detail, datasets);

  function resetEditForm() {
    setEditError("");
  }

  function beginEditSemanticModel() {
    resetEditForm();
    setShowEdit(true);
    setShowCreate(false);
    setEditSuccess("");
    setDeleteError("");
  }

  async function handleUpdateSemanticModel(payload) {
    if (!detail) {
      return;
    }
    setEditSubmitting(true);
    setEditError("");
    setEditSuccess("");
    setDeleteError("");
    try {
      const updated = await updateSemanticModel(String(detail.id || detail.name), {
        description: String(payload.description || "").trim() || null,
        datasets: payload.datasets,
        model: payload.model,
      });
      setDetail(updated);
      setData((current) => {
        const items = Array.isArray(current?.items) ? current.items : [];
        const nextItems = items.map((item) =>
          String(item?.id || item?.name) === String(updated?.id || updated?.name)
            ? updated
            : item,
        );
        return { items: nextItems, total: nextItems.length };
      });
      setShowEdit(false);
      setEditSuccess(`${updated.name} was updated.`);
      void reload();
    } catch (caughtError) {
      setEditError(getErrorMessage(caughtError));
    } finally {
      setEditSubmitting(false);
    }
  }

  async function handleDeleteSemanticModel() {
    if (!detail?.id || deleteSubmitting) {
      return;
    }
    const confirmed = window.confirm(
      `Delete runtime-managed semantic model '${detail.name}'? This cannot be undone.`,
    );
    if (!confirmed) {
      return;
    }
    setDeleteSubmitting(true);
    setDeleteError("");
    setEditSuccess("");
    try {
      await deleteSemanticModel(String(detail.id));
      setDetail(null);
      setShowEdit(false);
      setData((current) => {
        const items = Array.isArray(current?.items) ? current.items : [];
        const nextItems = items.filter(
          (item) => String(item?.id || item?.name) !== String(detail?.id || detail?.name),
        );
        return { items: nextItems, total: nextItems.length };
      });
      navigate("/semantic-models");
      void reload();
    } catch (caughtError) {
      setDeleteError(getErrorMessage(caughtError));
    } finally {
      setDeleteSubmitting(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadDetail() {
      if (!selected) {
        setDetail(null);
        return;
      }
      setDetailLoading(true);
      setDetailError("");
      try {
        const payload = await fetchSemanticModel(String(selected.id || selected.name));
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

    void loadDetail();

    return () => {
      cancelled = true;
    };
  }, [selected?.id, selected?.name]);

  return (
    <div className="page-stack">
      <section className="surface-panel product-command-bar">
        <div className="product-command-bar-main">
          <div className="product-command-bar-copy">
            <p className="eyebrow">Semantic Models</p>
            <h2>{selected?.name || "Semantic inventory"}</h2>
            <div className="product-command-bar-meta">
              <span className="chip">{formatValue(models.length)} models</span>
              <span className="chip">{formatValue(detail?.dataset_count || semanticDatasets.length)} datasets</span>
              <span className="chip">{formatValue(detail?.dimension_count || semanticFields.dimensions.length)} dimensions</span>
              <span className="chip">{formatValue(detail?.measure_count || semanticFields.measures.length)} measures</span>
            </div>
          </div>
          <div className="product-command-bar-actions">
            <button
              className="primary-button"
              type="button"
              onClick={() => {
                setShowCreate((current) => {
                  const nextValue = !current;
                  if (nextValue) {
                    setShowEdit(false);
                  }
                  return nextValue;
                });
                setCreateError("");
                setCreateSuccess("");
              }}
            >
              {showCreate ? "Close create flow" : "Create runtime-managed semantic model"}
            </button>
          </div>
        </div>
      </section>

      <section className="product-search-bar">
        <input
          className="text-input search-input"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Filter semantic models by name or dataset"
        />
        <button className="ghost-button" type="button" onClick={reload} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh semantic models"}
        </button>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="split-layout">
        <Panel title="Semantic models" className="list-panel compact-panel">
          <ManagementModeNotice
            mode={selected?.management_mode || "config_managed"}
            resourceLabel="Semantic model ownership"
          />
          {filteredModels.length > 0 ? (
            <div className="stack-list">
              {filteredModels.map((item) => (
                <Link
                  key={item.id || item.name}
                  className={`list-card ${selected?.id === item.id ? "active" : ""}`}
                  to={`/semantic-models/${buildItemRef(item)}`}
                >
                  <div className="list-card-topline">
                    <strong>{item.name}</strong>
                    <ManagementBadge mode={item.management_mode} />
                  </div>
                  <span>
                    {[
                      `${item.dataset_count || 0} datasets`,
                      `${item.measure_count || 0} measures`,
                      item.default ? "default" : null,
                    ]
                      .filter(Boolean)
                      .join(" | ")}
                  </span>
                  <small>{describeManagementMode(item.management_mode)}</small>
                </Link>
              ))}
            </div>
          ) : (
            <PageEmpty
              title="No semantic models"
              message="This runtime does not expose semantic model metadata yet."
            />
          )}
        </Panel>

        <div className="detail-stack">
          {createSuccess ? (
            <div className="callout success">
              <strong>Semantic model created</strong>
              <span>{createSuccess}</span>
            </div>
          ) : null}
          {editSuccess ? (
            <div className="callout success">
              <strong>Semantic model updated</strong>
              <span>{editSuccess}</span>
            </div>
          ) : null}

          {showCreate ? (
            <Panel
              title="Create runtime-managed semantic model"
              eyebrow="Create"
              actions={
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => {
                    setShowCreate(false);
                    resetCreateForm();
                  }}
                  disabled={createSubmitting}
                >
                  Cancel
                </button>
              }
            >
              <ManagementModeNotice mode="runtime_managed" resourceLabel="New semantic models" />
              <SemanticModelBuilder
                key={`create-${createResetKey}`}
                mode="create"
                initialState={buildSemanticModelBuilderState(null, datasets)}
                datasetOptions={datasets}
                submitting={createSubmitting}
                submitError={createError}
                submitLabel="Create semantic model"
                onSubmit={handleCreateSemanticModel}
                onCancel={() => {
                  setShowCreate(false);
                  resetCreateForm();
                }}
              />
            </Panel>
          ) : null}

          {showEdit && detail ? (
            <Panel
              title={`Edit ${detail.name}`}
              eyebrow="Edit"
              actions={
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => {
                    setShowEdit(false);
                    resetEditForm(detail);
                  }}
                  disabled={editSubmitting}
                >
                  Cancel
                </button>
              }
            >
              <ManagementModeNotice mode="runtime_managed" resourceLabel="Editable semantic model" />
              <SemanticModelBuilder
                key={`edit-${detail.id || detail.name}-${detail.updated_at || detail.updatedAt || "current"}`}
                mode="edit"
                initialState={editBuilderState}
                datasetOptions={datasets}
                submitting={editSubmitting}
                submitError={editError}
                submitLabel="Save semantic model"
                deleteSubmitting={deleteSubmitting}
                onSubmit={handleUpdateSemanticModel}
                onDelete={handleDeleteSemanticModel}
                onCancel={() => {
                  setShowEdit(false);
                  resetEditForm();
                }}
              />
            </Panel>
          ) : null}

          {selected ? (
            <>
              <Panel
                title={selected.name}
                className="compact-panel"
                actions={
                  <div className="panel-actions-inline">
                    <ManagementBadge mode={detail?.management_mode || selected.management_mode} />
                    {(detail?.management_mode || selected.management_mode) === "runtime_managed" ? (
                      <button className="ghost-button" type="button" onClick={beginEditSemanticModel}>
                        Edit
                      </button>
                    ) : null}
                  </div>
                }
              >
                {detailError ? <div className="error-banner">{detailError}</div> : null}
                {deleteError ? <div className="error-banner">{deleteError}</div> : null}
                {detailLoading ? (
                  <div className="empty-box">Loading semantic model detail...</div>
                ) : detail ? (
                  <>
                    <div className="inline-notes">
                      <span>{detail.default ? "Default runtime model" : "Secondary model"}</span>
                      <span>
                        {detail.dataset_count || semanticDatasets.length} semantic datasets
                      </span>
                      <span>
                        {detail.measure_count || semanticFields.measures.length} measures
                      </span>
                      <span>{describeManagementMode(detail.management_mode)}</span>
                    </div>
                    <DetailList
                      items={[
                        { label: "Description", value: formatValue(detail.description) },
                        { label: "Default", value: formatValue(detail.default) },
                        { label: "Datasets", value: formatList(detail.dataset_names) },
                        {
                          label: "Dimension count",
                          value: formatValue(detail.dimension_count),
                        },
                        { label: "Measure count", value: formatValue(detail.measure_count) },
                        {
                          label: "Management mode",
                          value: formatValue(detail.management_mode),
                        },
                      ]}
                    />
                    <div className="panel-actions-inline">
                      <button className="ghost-button" type="button" onClick={() => navigate("/dashboards")}>
                        Open Dashboard studio
                      </button>
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() => navigate("/chat")}
                      >
                        Open chat
                      </button>
                    </div>
                  </>
                ) : (
                  <PageEmpty
                    title="No detail"
                    message="The runtime did not return semantic model detail."
                  />
                )}
              </Panel>

              <ManagementModeNotice
                mode={detail?.management_mode || selected.management_mode}
                resourceLabel={selected.name}
              />

              <section className="summary-grid">
                <Panel title="Dataset explorer" eyebrow="Model structure">
                  {semanticDatasets.length > 0 ? (
                    <div className="detail-card-grid">
                      {semanticDatasets.map((item) => (
                        <article key={item.name} className="detail-card">
                          <strong>{item.name}</strong>
                          <span>{item.relationName || "No explicit relation name"}</span>
                          <div className="tag-list">
                            <span className="tag">{item.dimensions.length} dimensions</span>
                            <span className="tag">{item.measures.length} measures</span>
                          </div>
                          <small>
                            {[
                              item.dimensions
                                .slice(0, 3)
                                .map((field) => field.name)
                                .join(", "),
                              item.measures
                                .slice(0, 3)
                                .map((field) => field.name)
                                .join(", "),
                            ]
                              .filter(Boolean)
                              .join(" | ")}
                          </small>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <PageEmpty
                      title="No semantic datasets"
                      message="This model did not expose semantic dataset groups."
                    />
                  )}
                </Panel>

                <Panel title="Field inventory" eyebrow="Dimensions and measures">
                  {semanticFields.dimensions.length > 0 ||
                  semanticFields.measures.length > 0 ? (
                    <div className="field-section-list">
                      <div className="field-group">
                        <div className="field-group-header">
                          <strong>Dimensions</strong>
                          <span>{semanticFields.dimensions.length}</span>
                        </div>
                        <div className="field-pill-list">
                          {semanticFields.dimensions.map((item) => (
                            <span key={item.value} className="field-pill static">
                              {item.label}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="field-group">
                        <div className="field-group-header">
                          <strong>Measures</strong>
                          <span>{semanticFields.measures.length}</span>
                        </div>
                        <div className="field-pill-list">
                          {semanticFields.measures.map((item) => (
                            <span key={item.value} className="field-pill static">
                              {item.label}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <PageEmpty
                      title="No fields exposed"
                      message="This model did not expose dimensions or measures."
                    />
                  )}
                </Panel>
              </section>

              <Panel title="Semantic workspace" eyebrow="Inspect">
                <SectionTabs
                  tabs={[
                    { value: "overview", label: "Overview" },
                    { value: "datasets", label: "Datasets" },
                    { value: "fields", label: "Fields" },
                    { value: "yaml", label: "YAML" },
                    { value: "json", label: "JSON" },
                  ]}
                  value={activeTab}
                  onChange={setActiveTab}
                />

                {activeTab === "overview" ? (
                  <div className="detail-card-grid">
                    {semanticDatasets.map((item) => (
                      <article key={item.name} className="detail-card">
                        <strong>{item.name}</strong>
                        <span>{item.relationName || "No relation name provided"}</span>
                        <div className="tag-list">
                          <span className="tag">{item.dimensions.length} dimensions</span>
                          <span className="tag">{item.measures.length} measures</span>
                        </div>
                        <small>
                          {[
                            item.dimensions
                              .slice(0, 3)
                              .map((field) => field.name)
                              .join(", "),
                            item.measures
                              .slice(0, 3)
                              .map((field) => field.name)
                              .join(", "),
                          ]
                            .filter(Boolean)
                            .join(" | ")}
                        </small>
                      </article>
                    ))}
                  </div>
                ) : null}

                {activeTab === "datasets" ? (
                  filteredSemanticDatasets.length > 0 ? (
                    <div className="field-section-list">
                      {filteredSemanticDatasets.map((dataset) => (
                        <div key={dataset.name} className="field-group">
                          <div className="field-group-header">
                            <strong>{dataset.name}</strong>
                            <span>{dataset.relationName || "semantic dataset"}</span>
                          </div>
                          <div className="tag-list">
                            <span className="tag">{dataset.dimensions.length} dimensions</span>
                            <span className="tag">{dataset.measures.length} measures</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <PageEmpty
                      title="No semantic datasets"
                      message="This model did not expose semantic dataset groups."
                    />
                  )
                ) : null}

                {activeTab === "fields" ? (
                  <div className="page-stack">
                    <label className="field">
                      <span>Find fields</span>
                      <input
                        className="text-input"
                        type="search"
                        value={fieldSearch}
                        onChange={(event) => setFieldSearch(event.target.value)}
                        placeholder="Filter datasets, dimensions, or measures"
                      />
                    </label>
                    {filteredSemanticDatasets.length > 0 ? (
                      <div className="field-section-list">
                        {filteredSemanticDatasets.map((dataset) => (
                          <div key={`${dataset.name}-fields`} className="field-group">
                            <div className="field-group-header">
                              <strong>{dataset.name}</strong>
                              <span>{dataset.relationName || "semantic dataset"}</span>
                            </div>
                            <div className="field-pill-list">
                              {dataset.dimensions.map((item) => (
                                <span
                                  key={`${dataset.name}-${item.name}-dimension`}
                                  className="field-pill static"
                                >
                                  {item.name}
                                </span>
                              ))}
                              {dataset.measures.map((item) => (
                                <span
                                  key={`${dataset.name}-${item.name}-measure`}
                                  className="field-pill static"
                                >
                                  {item.name}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <PageEmpty title="No fields found" message="Adjust the filter or switch models." />
                    )}
                  </div>
                ) : null}

                {activeTab === "yaml" ? (
                  detail?.content_yaml ? (
                    <pre className="code-block">{detail.content_yaml}</pre>
                  ) : (
                    <PageEmpty
                      title="No YAML available"
                      message="This semantic model did not expose YAML content."
                    />
                  )
                ) : null}

                {activeTab === "json" ? (
                  detail?.content_json ? (
                    <pre className="code-block">{renderJson(detail.content_json)}</pre>
                  ) : (
                    <PageEmpty
                      title="No JSON payload"
                      message="This semantic model did not expose a JSON representation."
                    />
                  )
                ) : null}
              </Panel>
            </>
          ) : (
            <Panel title="Semantic model detail" eyebrow="Runtime">
              <PageEmpty
                title="No model selected"
                message="Pick a semantic model to inspect its runtime definition."
              />
            </Panel>
          )}
        </div>
      </section>
    </div>
  );
}
