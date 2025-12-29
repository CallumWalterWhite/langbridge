'use client';

import { JSX, useCallback, useEffect, useMemo, useState } from 'react';
import yaml from 'js-yaml';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useWorkspaceScope } from '@/context/workspaceScope';
import {
  createSemanticModel,
  deleteSemanticModel,
  fetchSemanticModelYaml,
  generateSemanticModelYaml,
  listSemanticModels,
} from '@/orchestration/semanticModels';
import type {
  SemanticDimension,
  SemanticMeasure,
  SemanticMetric,
  SemanticModelRecord,
  SemanticRelationship,
  SemanticTable,
} from '@/orchestration/semanticModels/types';
import { fetchConnectors } from '@/orchestration/connectors';
import type { ConnectorResponse } from '@/orchestration/connectors/types';
import { ApiError } from '@/orchestration/http';
import { cn, formatRelativeDate } from '@/lib/utils';

interface FormState {
  name: string;
  description: string;
}

interface BuilderDimension extends SemanticDimension {
  id: string;
}

interface BuilderMeasure extends SemanticMeasure {
  id: string;
}

type RelationshipType = 'one_to_many' | 'many_to_one' | 'one_to_one' | 'many_to_many';

interface BuilderTable extends Omit<SemanticTable, 'dimensions' | 'measures'> {
  id: string;
  entityName: string;
  dimensions: BuilderDimension[];
  measures: BuilderMeasure[];
}

interface BuilderRelationship extends Omit<SemanticRelationship, 'type'> {
  id: string;
  type: RelationshipType;
}

interface BuilderMetric extends SemanticMetric {
  id: string;
  name: string;
}

interface BuilderModel {
  version: string;
  description?: string;
  tables: BuilderTable[];
  relationships: BuilderRelationship[];
  metrics: BuilderMetric[];
}

const RELATIONSHIP_TYPES: RelationshipType[] = ['one_to_many', 'many_to_one', 'one_to_one', 'many_to_many'];
const DEFAULT_MODEL_VERSION = '1.0';

export default function SemanticModelPage(): JSX.Element {
  const { selectedOrganizationId, selectedProjectId, organizations, loading: scopeLoading } = useWorkspaceScope();

  const [formState, setFormState] = useState<FormState>({ name: '', description: '' });
  const [connectors, setConnectors] = useState<ConnectorResponse[]>([]);
  const [connectorsLoading, setConnectorsLoading] = useState(false);
  const [selectedConnectorId, setSelectedConnectorId] = useState('');
  const [builder, setBuilder] = useState<BuilderModel>(() => createEmptyBuilderModel());
  const [storedModels, setStoredModels] = useState<SemanticModelRecord[]>([]);
  const [storedLoading, setStoredLoading] = useState(false);
  const [autoGenerating, setAutoGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);

  const organizationAvailable = Boolean(selectedOrganizationId);

  const currentOrganizationName = useMemo(() => {
    if (!selectedOrganizationId) {
      return 'Select an organization';
    }
    return organizations.find((org) => org.id === selectedOrganizationId)?.name ?? 'Unknown organization';
  }, [organizations, selectedOrganizationId]);

  const selectedConnector = useMemo(
    () => connectors.find((connector) => connector.id === selectedConnectorId),
    [connectors, selectedConnectorId],
  );

  const connectorLookup = useMemo(
    () =>
      connectors.reduce<Record<string, string>>((acc, connector) => {
        if (connector.id) {
          acc[connector.id] = connector.name;
        }
        return acc;
      }, {}),
    [connectors],
  );

  const builderYamlPreview = useMemo(() => {
    try {
      return {
        yaml: serializeBuilderModel(builder, selectedConnector?.name),
        error: null,
      };
    } catch (err) {
      return {
        yaml: '',
        error: err instanceof Error ? err.message : 'Unable to build YAML preview.',
      };
    }
  }, [builder, selectedConnector?.name]);

  const loadConnectors = useCallback(async () => {
    if (!selectedOrganizationId) {
      return;
    }
    setConnectorsLoading(true);
    try {
      const data = await fetchConnectors(selectedOrganizationId);
      setConnectors(data);
      setSelectedConnectorId((current) => {
        if (current) {
          return current;
        }
        const firstUsable = data.find((connector) => connector.id);
        return firstUsable?.id ?? '';
      });
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setConnectorsLoading(false);
    }
  }, [selectedOrganizationId]);

  const refreshStoredModels = useCallback(async () => {
    if (!selectedOrganizationId) {
      setStoredModels([]);
      return;
    }
    setStoredLoading(true);
    try {
      const models = await listSemanticModels(selectedOrganizationId, selectedProjectId ?? undefined);
      setStoredModels(models);
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setStoredLoading(false);
    }
  }, [selectedOrganizationId, selectedProjectId]);

  useEffect(() => {
    if (!selectedOrganizationId) {
      setConnectors([]);
      setSelectedConnectorId('');
      return;
    }
    setSelectedConnectorId('');
    void loadConnectors();
  }, [selectedOrganizationId, loadConnectors]);

  useEffect(() => {
    if (!selectedOrganizationId) {
      setStoredModels([]);
      return;
    }
    void refreshStoredModels();
  }, [selectedOrganizationId, selectedProjectId, refreshStoredModels]);

  useEffect(() => {
    setBuilder(createEmptyBuilderModel());
  }, [selectedConnectorId]);

  useEffect(() => {
    setIsClient(true);
  }, []);

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) {
      setError('Select an organization before saving a semantic model.');
      return;
    }
    if (!selectedConnectorId) {
      setError('Select a connector before saving a semantic model.');
      return;
    }
    if (!formState.name.trim()) {
      setError('Provide a name for the semantic model.');
      return;
    }

    try {
      validateBuilderModel(builder);
    } catch (validationError) {
      setError(
        validationError instanceof Error
          ? validationError.message
          : 'Semantic builder is incomplete. Add at least one table.',
      );
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const yamlPayload = serializeBuilderModel(builder, selectedConnector?.name);
      await createSemanticModel({
        organizationId: selectedOrganizationId,
        projectId: selectedProjectId ?? null,
        connectorId: selectedConnectorId,
        name: formState.name.trim(),
        description: formState.description.trim() || undefined,
        modelYaml: yamlPayload,
        autoGenerate: false,
      });
      await refreshStoredModels();
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSubmitting(false);
    }
  }

  const handleAutoGenerate = useCallback(async () => {
    if (!selectedConnectorId) {
      setError('Select a connector before generating a semantic model.');
      return;
    }
    setAutoGenerating(true);
    setError(null);
    try {
      const yamlText = await generateSemanticModelYaml(selectedConnectorId);
      const generatedModel = parseYamlToBuilderModel(yamlText);
      setBuilder(generatedModel);
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setAutoGenerating(false);
    }
  }, [selectedConnectorId]);

  async function handleDelete(modelId: string) {
    if (!selectedOrganizationId) {
      return;
    }
    try {
      await deleteSemanticModel(modelId, selectedOrganizationId);
      await refreshStoredModels();
    } catch (err) {
      setError(resolveError(err));
    }
  }

  async function handleDownloadYaml(modelId: string, name: string) {
    if (!selectedOrganizationId) {
      return;
    }
    try {
      const yamlText = await fetchSemanticModelYaml(modelId, selectedOrganizationId);
      const blob = new Blob([yamlText], { type: 'text/yaml;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${name.replace(/\s+/g, '_').toLowerCase()}.yml`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(resolveError(err));
    }
  }

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-[color:var(--text-primary)]">Semantic model builder</h1>
        <p className="max-w-3xl text-sm">
          Describe the semantic layer for a connector and LangBridge will persist the YAML definition for your agents.
          Choose a connector, tune dimensions and measures, then review the YAML output before saving.
        </p>
        <div className="text-xs text-[color:var(--text-muted)]">
          Scope: <span className="font-medium text-[color:var(--text-primary)]">{currentOrganizationName}</span>
          {selectedProjectId ? ' · project scoped' : ' · organization scoped'}
        </div>
      </header>

      {error ? (
        <div className="rounded-lg border border-rose-300 bg-rose-100/40 px-4 py-3 text-sm text-rose-700">{error}</div>
      ) : null}

      {!organizationAvailable && !scopeLoading ? (
        <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-center text-sm">
          Choose an organization from the scope selector to begin modeling.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <section className="space-y-6 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
            <form className="space-y-6" onSubmit={(event) => void handleSave(event)}>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">1. Select a connector</h2>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void loadConnectors()}
                    isLoading={connectorsLoading}
                  >
                    Refresh list
                  </Button>
                </div>
                <p className="text-sm">
                  Each semantic model is tied to one connector. Pick a connector to unlock the builder and optional
                  auto-generation.
                </p>
                {connectors.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-6 text-sm">
                    No connectors available in this scope. Create a connector first, then return to build a semantic
                    model.
                  </div>
                ) : (
                  <div className="grid gap-3 md:grid-cols-2">
                    {connectors.map((connector) => {
                      const connectorId = connector.id ?? '';
                      const isSelected = connectorId !== '' && connectorId === selectedConnectorId;
                      return (
                        <button
                          key={connector.id ?? connector.name}
                          type="button"
                          className={cn(
                            'rounded-2xl border bg-[color:var(--panel-alt)] p-4 text-left transition hover:border-[color:var(--border-strong)]',
                            isSelected ? 'border-[color:var(--accent)] shadow-soft' : 'border-[color:var(--panel-border)]',
                          )}
                          onClick={() => setSelectedConnectorId(connectorId)}
                          disabled={!connectorId}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                                {connector.name}
                              </p>
                              <p className="text-xs text-[color:var(--text-muted)]">
                                {connector.description ?? 'No description provided.'}
                              </p>
                            </div>
                            {isSelected ? <Badge variant="secondary">Selected</Badge> : null}
                          </div>
                          <div className="mt-3 text-xs text-[color:var(--text-muted)]">
                            Type: <span className="text-[color:var(--text-primary)]">{connector.connectorType ?? 'Custom'}</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
              {!selectedConnectorId ? (
                <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-6 text-sm">
                  Select a connector to start configuring the semantic model.
                </div>
              ) : (
                <>
                  <div className="space-y-4 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h3 className="text-base font-semibold text-[color:var(--text-primary)]">2. Model metadata</h3>
                        <p className="text-xs text-[color:var(--text-muted)]">
                          Name and describe the saved record plus the semantic layer version.
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => void handleAutoGenerate()}
                        isLoading={autoGenerating}
                      >
                        Auto-generate YAML
                      </Button>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="model-name">Model name</Label>
                        <Input
                          id="model-name"
                          value={formState.name}
                          onChange={(event) =>
                            setFormState((current) => ({ ...current, name: event.target.value }))
                          }
                          placeholder="e.g. Sales semantic layer"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="model-description">Record description</Label>
                        <Input
                          id="model-description"
                          value={formState.description}
                          onChange={(event) =>
                            setFormState((current) => ({ ...current, description: event.target.value }))
                          }
                          placeholder="This text appears when browsing saved models."
                        />
                      </div>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="semantic-version">Semantic version</Label>
                        <Input
                          id="semantic-version"
                          value={builder.version}
                          onChange={(event) =>
                            setBuilder((current) => ({ ...current, version: event.target.value || DEFAULT_MODEL_VERSION }))
                          }
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="semantic-description">Semantic description</Label>
                        <Textarea
                          id="semantic-description"
                          rows={3}
                          value={builder.description ?? ''}
                          onChange={(event) =>
                            setBuilder((current) => ({ ...current, description: event.target.value }))
                          }
                          placeholder="Optional context for how agents should interpret this model."
                        />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-semibold text-[color:var(--text-primary)]">3. Tables</h3>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setBuilder((current) => ({
                            ...current,
                            tables: [...current.tables, createEmptyTable(current.tables.length + 1)],
                          }))
                        }
                      >
                        Add table
                      </Button>
                    </div>
                    {builder.tables.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-6 text-sm">
                        No tables yet. Add an entity to start defining dimensions and measures.
                      </div>
                    ) : (
                      builder.tables.map((table, index) => (
                        <article
                          key={table.id}
                          className="space-y-4 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-5 shadow-soft"
                        >
                          <header className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                                {table.entityName || `Table ${index + 1}`}
                              </p>
                              <p className="text-xs text-[color:var(--text-muted)]">
                                {table.schema && table.name ? `${table.schema}.${table.name}` : 'Define schema and table name'}
                              </p>
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                setBuilder((current) => ({
                                  ...current,
                                  tables: current.tables.filter((entry) => entry.id !== table.id),
                                }))
                              }
                            >
                              Remove
                            </Button>
                          </header>

                          <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-1">
                              <Label htmlFor={`entity-${table.id}`}>Entity name</Label>
                              <Input
                                id={`entity-${table.id}`}
                                value={table.entityName}
                                onChange={(event) =>
                                  setBuilder((current) => ({
                                    ...current,
                                    tables: current.tables.map((entry) =>
                                      entry.id === table.id ? { ...entry, entityName: event.target.value } : entry,
                                    ),
                                  }))
                                }
                                placeholder="Alias used inside YAML"
                              />
                            </div>
                            <div className="space-y-1">
                              <Label htmlFor={`schema-${table.id}`}>Schema</Label>
                              <Input
                                id={`schema-${table.id}`}
                                value={table.schema}
                                onChange={(event) =>
                                  setBuilder((current) => ({
                                    ...current,
                                    tables: current.tables.map((entry) =>
                                      entry.id === table.id ? { ...entry, schema: event.target.value } : entry,
                                    ),
                                  }))
                                }
                                placeholder="e.g. analytics"
                              />
                            </div>
                            <div className="space-y-1">
                              <Label htmlFor={`table-${table.id}`}>Table name</Label>
                              <Input
                                id={`table-${table.id}`}
                                value={table.name}
                                onChange={(event) =>
                                  setBuilder((current) => ({
                                    ...current,
                                    tables: current.tables.map((entry) =>
                                      entry.id === table.id ? { ...entry, name: event.target.value } : entry,
                                    ),
                                  }))
                                }
                                placeholder="e.g. orders"
                              />
                            </div>
                            <div className="space-y-1">
                              <Label htmlFor={`table-description-${table.id}`}>Description</Label>
                              <Textarea
                                id={`table-description-${table.id}`}
                                rows={3}
                                value={table.description ?? ''}
                                onChange={(event) =>
                                  setBuilder((current) => ({
                                    ...current,
                                    tables: current.tables.map((entry) =>
                                      entry.id === table.id ? { ...entry, description: event.target.value } : entry,
                                    ),
                                  }))
                                }
                              />
                            </div>
                          </div>

                          <div className="grid gap-4 lg:grid-cols-2">
                            <div className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--surface-muted)] p-4">
                              <div className="mb-3 flex items-center justify-between">
                                <h4 className="text-sm font-semibold text-[color:var(--text-primary)]">
                                  Dimensions ({table.dimensions.length})
                                </h4>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    setBuilder((current) => ({
                                      ...current,
                                      tables: current.tables.map((entry) =>
                                        entry.id === table.id
                                          ? {
                                              ...entry,
                                              dimensions: [
                                                ...entry.dimensions,
                                                {
                                                  id: createId('dimension'),
                                                  name: '',
                                                  type: '',
                                                  primaryKey: false,
                                                  vectorized: false,
                                                },
                                              ],
                                            }
                                          : entry,
                                      ),
                                    }))
                                  }
                                >
                                  Add dimension
                                </Button>
                              </div>
                              {table.dimensions.length === 0 ? (
                                <p className="text-xs text-[color:var(--text-muted)]">No dimensions yet.</p>
                              ) : (
                                <div className="space-y-3">
                                  {table.dimensions.map((dimension) => (
                                    <div
                                      key={dimension.id}
                                      className="rounded-lg border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-3"
                                    >
                                      <div className="flex items-center justify-between gap-3">
                                        <Label className="text-xs font-semibold uppercase tracking-wide">
                                          Dimension
                                        </Label>
                                        <Button
                                          type="button"
                                          variant="ghost"
                                          size="sm"
                                          onClick={() =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) =>
                                                entry.id === table.id
                                                  ? {
                                                      ...entry,
                                                      dimensions: entry.dimensions.filter(
                                                        (item) => item.id !== dimension.id,
                                                      ),
                                                    }
                                                  : entry,
                                              ),
                                            }))
                                          }
                                        >
                                          Remove
                                        </Button>
                                      </div>
                                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                                        <Input
                                          value={dimension.name}
                                          onChange={(event) =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) => {
                                                if (entry.id !== table.id) {
                                                  return entry;
                                                }
                                                return {
                                                  ...entry,
                                                  dimensions: entry.dimensions.map((item) =>
                                                    item.id === dimension.id ? { ...item, name: event.target.value } : item,
                                                  ),
                                                };
                                              }),
                                            }))
                                          }
                                          placeholder="Name"
                                        />
                                        <Input
                                          value={dimension.type}
                                          onChange={(event) =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) => {
                                                if (entry.id !== table.id) {
                                                  return entry;
                                                }
                                                return {
                                                  ...entry,
                                                  dimensions: entry.dimensions.map((item) =>
                                                    item.id === dimension.id ? { ...item, type: event.target.value } : item,
                                                  ),
                                                };
                                              }),
                                            }))
                                          }
                                          placeholder="Type e.g. string"
                                        />
                                      </div>
                                      <Textarea
                                        className="mt-3"
                                        rows={2}
                                        value={dimension.description ?? ''}
                                        onChange={(event) =>
                                          setBuilder((current) => ({
                                            ...current,
                                            tables: current.tables.map((entry) => {
                                              if (entry.id !== table.id) {
                                                return entry;
                                              }
                                              return {
                                                ...entry,
                                                dimensions: entry.dimensions.map((item) =>
                                                  item.id === dimension.id
                                                    ? { ...item, description: event.target.value }
                                                    : item,
                                                ),
                                              };
                                            }),
                                          }))
                                        }
                                        placeholder="Description"
                                      />
                                      <label className="mt-3 flex items-center gap-2 text-xs font-medium text-[color:var(--text-primary)]">
                                        <input
                                          type="checkbox"
                                          checked={Boolean(dimension.primaryKey)}
                                          onChange={(event) =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) => {
                                                if (entry.id !== table.id) {
                                                  return entry;
                                                }
                                                return {
                                                  ...entry,
                                                  dimensions: entry.dimensions.map((item) =>
                                                    item.id === dimension.id
                                                      ? { ...item, primaryKey: event.target.checked }
                                                      : item,
                                                  ),
                                                };
                                              }),
                                            }))
                                          }
                                        />
                                        Primary key
                                      </label>
                                      <label className="mt-2 flex items-center gap-2 text-xs font-medium text-[color:var(--text-primary)]">
                                        <input
                                          type="checkbox"
                                          checked={Boolean(dimension.vectorized)}
                                          onChange={(event) =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) => {
                                                if (entry.id !== table.id) {
                                                  return entry;
                                                }
                                                return {
                                                  ...entry,
                                                  dimensions: entry.dimensions.map((item) =>
                                                    item.id === dimension.id
                                                      ? { ...item, vectorized: event.target.checked }
                                                      : item,
                                                  ),
                                                };
                                              }),
                                            }))
                                          }
                                        />
                                        Vectorize values for semantic search
                                      </label>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                            <div className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--surface-muted)] p-4">
                              <div className="mb-3 flex items-center justify-between">
                                <h4 className="text-sm font-semibold text-[color:var(--text-primary)]">
                                  Measures ({table.measures.length})
                                </h4>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    setBuilder((current) => ({
                                      ...current,
                                      tables: current.tables.map((entry) =>
                                        entry.id === table.id
                                          ? {
                                              ...entry,
                                              measures: [
                                                ...entry.measures,
                                                {
                                                  id: createId('measure'),
                                                  name: '',
                                                  type: '',
                                                  aggregation: '',
                                                },
                                              ],
                                            }
                                          : entry,
                                      ),
                                    }))
                                  }
                                >
                                  Add measure
                                </Button>
                              </div>
                              {table.measures.length === 0 ? (
                                <p className="text-xs text-[color:var(--text-muted)]">No measures yet.</p>
                              ) : (
                                <div className="space-y-3">
                                  {table.measures.map((measure) => (
                                    <div
                                      key={measure.id}
                                      className="rounded-lg border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-3"
                                    >
                                      <div className="flex items-center justify-between gap-3">
                                        <Label className="text-xs font-semibold uppercase tracking-wide">Measure</Label>
                                        <Button
                                          type="button"
                                          variant="ghost"
                                          size="sm"
                                          onClick={() =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) =>
                                                entry.id === table.id
                                                  ? {
                                                      ...entry,
                                                      measures: entry.measures.filter((item) => item.id !== measure.id),
                                                    }
                                                  : entry,
                                              ),
                                            }))
                                          }
                                        >
                                          Remove
                                        </Button>
                                      </div>
                                      <div className="mt-3 grid gap-3 md:grid-cols-3">
                                        <Input
                                          value={measure.name}
                                          onChange={(event) =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) => {
                                                if (entry.id !== table.id) {
                                                  return entry;
                                                }
                                                return {
                                                  ...entry,
                                                  measures: entry.measures.map((item) =>
                                                    item.id === measure.id ? { ...item, name: event.target.value } : item,
                                                  ),
                                                };
                                              }),
                                            }))
                                          }
                                          placeholder="Name"
                                        />
                                        <Input
                                          value={measure.type}
                                          onChange={(event) =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) => {
                                                if (entry.id !== table.id) {
                                                  return entry;
                                                }
                                                return {
                                                  ...entry,
                                                  measures: entry.measures.map((item) =>
                                                    item.id === measure.id ? { ...item, type: event.target.value } : item,
                                                  ),
                                                };
                                              }),
                                            }))
                                          }
                                          placeholder="Type"
                                        />
                                        <Input
                                          value={measure.aggregation ?? ''}
                                          onChange={(event) =>
                                            setBuilder((current) => ({
                                              ...current,
                                              tables: current.tables.map((entry) => {
                                                if (entry.id !== table.id) {
                                                  return entry;
                                                }
                                                return {
                                                  ...entry,
                                                  measures: entry.measures.map((item) =>
                                                    item.id === measure.id
                                                      ? { ...item, aggregation: event.target.value }
                                                      : item,
                                                  ),
                                                };
                                              }),
                                            }))
                                          }
                                          placeholder="Aggregation e.g. sum"
                                        />
                                      </div>
                                      <Textarea
                                        className="mt-3"
                                        rows={2}
                                        value={measure.description ?? ''}
                                        onChange={(event) =>
                                          setBuilder((current) => ({
                                            ...current,
                                            tables: current.tables.map((entry) => {
                                              if (entry.id !== table.id) {
                                                return entry;
                                              }
                                              return {
                                                ...entry,
                                                measures: entry.measures.map((item) =>
                                                  item.id === measure.id
                                                    ? { ...item, description: event.target.value }
                                                    : item,
                                                ),
                                              };
                                            }),
                                          }))
                                        }
                                        placeholder="Description"
                                      />
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </article>
                      ))
                    )}
                  </div>
                  <div className="space-y-4 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h3 className="text-base font-semibold text-[color:var(--text-primary)]">4. Joins</h3>
                        <p className="text-xs text-[color:var(--text-muted)]">
                          Map how these entities relate so downstream tools can combine tables safely.
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={builder.tables.length === 0}
                        onClick={() =>
                          setBuilder((current) => ({
                            ...current,
                            relationships: [
                              ...current.relationships,
                              createEmptyRelationship(current.relationships.length + 1),
                            ],
                          }))
                        }
                      >
                        Add join
                      </Button>
                    </div>
                    {builder.relationships.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--surface-muted)] p-4 text-sm">
                        No joins configured yet. Add at least one join to describe how tables connect.
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {builder.relationships.map((relationship, index) => (
                          <div
                            key={relationship.id}
                            className="space-y-3 rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                                  {relationship.name || `Join ${index + 1}`}
                                </p>
                                <p className="text-xs text-[color:var(--text-muted)]">
                                  {relationship.from && relationship.to
                                    ? `${relationship.from} → ${relationship.to}`
                                    : 'Define the source and target entities'}
                                </p>
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  setBuilder((current) => ({
                                    ...current,
                                    relationships: current.relationships.filter((entry) => entry.id !== relationship.id),
                                  }))
                                }
                              >
                                Remove
                              </Button>
                            </div>
                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="space-y-1">
                                <Label htmlFor={`join-name-${relationship.id}`}>Join name</Label>
                                <Input
                                  id={`join-name-${relationship.id}`}
                                  value={relationship.name}
                                  onChange={(event) =>
                                    setBuilder((current) => ({
                                      ...current,
                                      relationships: current.relationships.map((entry) =>
                                        entry.id === relationship.id ? { ...entry, name: event.target.value } : entry,
                                      ),
                                    }))
                                  }
                                  placeholder="sales_to_customers"
                                />
                              </div>
                              <div className="space-y-1">
                                <Label htmlFor={`join-type-${relationship.id}`}>Cardinality</Label>
                                <Select
                                  id={`join-type-${relationship.id}`}
                                  placeholder="Select cardinality"
                                  value={relationship.type}
                                  onChange={(event) =>
                                    setBuilder((current) => ({
                                      ...current,
                                      relationships: current.relationships.map((entry) =>
                                        entry.id === relationship.id
                                          ? { ...entry, type: event.target.value as RelationshipType }
                                          : entry,
                                      ),
                                    }))
                                  }
                                >
                                  {RELATIONSHIP_TYPES.map((type) => (
                                    <option key={type} value={type}>
                                      {type.replace(/_/g, ' ')}
                                    </option>
                                  ))}
                                </Select>
                              </div>
                            </div>
                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="space-y-1">
                                <Label htmlFor={`join-from-${relationship.id}`}>From entity</Label>
                                <Input
                                  id={`join-from-${relationship.id}`}
                                  value={relationship.from}
                                  onChange={(event) =>
                                    setBuilder((current) => ({
                                      ...current,
                                      relationships: current.relationships.map((entry) =>
                                        entry.id === relationship.id ? { ...entry, from: event.target.value } : entry,
                                      ),
                                    }))
                                  }
                                  placeholder="_main_sales"
                                />
                              </div>
                              <div className="space-y-1">
                                <Label htmlFor={`join-to-${relationship.id}`}>To entity</Label>
                                <Input
                                  id={`join-to-${relationship.id}`}
                                  value={relationship.to}
                                  onChange={(event) =>
                                    setBuilder((current) => ({
                                      ...current,
                                      relationships: current.relationships.map((entry) =>
                                        entry.id === relationship.id ? { ...entry, to: event.target.value } : entry,
                                      ),
                                    }))
                                  }
                                  placeholder="_main_customers"
                                />
                              </div>
                            </div>
                            <div className="space-y-1">
                              <Label htmlFor={`join-condition-${relationship.id}`}>Join condition</Label>
                              <Textarea
                                id={`join-condition-${relationship.id}`}
                                rows={2}
                                value={relationship.joinOn}
                                onChange={(event) =>
                                  setBuilder((current) => ({
                                    ...current,
                                    relationships: current.relationships.map((entry) =>
                                      entry.id === relationship.id ? { ...entry, joinOn: event.target.value } : entry,
                                    ),
                                  }))
                                }
                                placeholder="_main_sales.customer_id = _main_customers.customer_id"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="space-y-4 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-semibold text-[color:var(--text-primary)]">5. Metrics</h3>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setBuilder((current) => ({
                            ...current,
                            metrics: [
                              ...current.metrics,
                              {
                                id: createId('metric'),
                                name: '',
                                expression: '',
                              },
                            ],
                          }))
                        }
                      >
                        Add metric
                      </Button>
                    </div>
                    {builder.metrics.length === 0 ? (
                      <p className="text-sm text-[color:var(--text-muted)]">No derived metrics defined.</p>
                    ) : (
                      <div className="space-y-3">
                        {builder.metrics.map((metric) => (
                          <div
                            key={metric.id}
                            className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                          >
                            <div className="flex items-center justify-between">
                              <Label className="text-xs font-semibold uppercase tracking-wide">Metric</Label>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  setBuilder((current) => ({
                                    ...current,
                                    metrics: current.metrics.filter((item) => item.id !== metric.id),
                                  }))
                                }
                              >
                                Remove
                              </Button>
                            </div>
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              <Input
                                value={metric.name}
                                onChange={(event) =>
                                  setBuilder((current) => ({
                                    ...current,
                                    metrics: current.metrics.map((item) =>
                                      item.id === metric.id ? { ...item, name: event.target.value } : item,
                                    ),
                                  }))
                                }
                                placeholder="Metric name"
                              />
                              <Input
                                value={metric.description ?? ''}
                                onChange={(event) =>
                                  setBuilder((current) => ({
                                    ...current,
                                    metrics: current.metrics.map((item) =>
                                      item.id === metric.id ? { ...item, description: event.target.value } : item,
                                    ),
                                  }))
                                }
                                placeholder="Description"
                              />
                            </div>
                            <Textarea
                              className="mt-3"
                              rows={3}
                              value={metric.expression}
                              onChange={(event) =>
                                setBuilder((current) => ({
                                  ...current,
                                  metrics: current.metrics.map((item) =>
                                    item.id === metric.id ? { ...item, expression: event.target.value } : item,
                                  ),
                                }))
                              }
                              placeholder="SQL expression referencing table columns"
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-semibold text-[color:var(--text-primary)]">6. YAML preview</h3>
                      <span className="text-xs text-[color:var(--text-muted)]">Read-only export used for the API</span>
                    </div>
                    {builderYamlPreview.error ? (
                      <p className="text-xs text-rose-600">{builderYamlPreview.error}</p>
                    ) : null}
                    <Textarea rows={12} readOnly value={builderYamlPreview.yaml} className="font-mono text-xs" />
                    <Button type="submit" className="w-full" isLoading={submitting} disabled={!selectedConnectorId}>
                      Save semantic model
                    </Button>
                  </div>
                </>
              )}
            </form>
          </section>
          <aside className="space-y-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">Saved models</h2>
              <Badge variant="secondary">{storedModels.length}</Badge>
            </div>
            {storedLoading ? (
              <p className="text-sm">Loading saved models...</p>
            ) : storedModels.length === 0 ? (
              <p className="text-sm text-[color:var(--text-muted)]">No saved models yet.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {storedModels.map((model) => (
                  <li
                    key={model.id}
                    className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-[color:var(--text-primary)]">{model.name}</p>
                        <p className="text-xs text-[color:var(--text-muted)]">
                          {isClient ? `Saved ${formatRelativeDate(model.updatedAt)}` : ''}
                          {connectorLookup[model.connectorId] ? ` · ${connectorLookup[model.connectorId]}` : ''}
                        </p>
                        {model.description ? (
                          <p className="mt-2 text-xs text-[color:var(--text-secondary)]">{model.description}</p>
                        ) : null}
                      </div>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => void handleDownloadYaml(model.id, model.name)}
                        >
                          Download YAML
                        </Button>
                        <Button type="button" variant="ghost" size="sm" onClick={() => void handleDelete(model.id)}>
                          Remove
                        </Button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
function resolveError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong while processing your request.';
}

function createId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

function createEmptyBuilderModel(): BuilderModel {
  return {
    version: DEFAULT_MODEL_VERSION,
    description: '',
    tables: [],
    relationships: [],
    metrics: [],
  };
}

function createEmptyRelationship(position: number): BuilderRelationship {
  return {
    id: createId('relationship'),
    name: `join_${position}`,
    from: '',
    to: '',
    type: 'many_to_one',
    joinOn: '',
  };
}

function createEmptyTable(position: number): BuilderTable {
  return {
    id: createId('table'),
    entityName: `entity_${position}`,
    schema: '',
    name: '',
    description: '',
    synonyms: null,
    filters: null,
    dimensions: [],
    measures: [],
  };
}

function tableHasContent(table: BuilderTable): boolean {
  return Boolean(
    table.entityName.trim() ||
      table.schema.trim() ||
      table.name.trim() ||
      table.dimensions.length > 0 ||
      table.measures.length > 0,
  );
}

function validateBuilderModel(builder: BuilderModel): void {
  const populatedTables = builder.tables.filter(tableHasContent);
  if (populatedTables.length === 0) {
    throw new Error('Add at least one table with dimensions or measures.');
  }
  populatedTables.forEach((table) => {
    if (!table.entityName.trim() || !table.schema.trim() || !table.name.trim()) {
      throw new Error('Each table must include an entity name, schema, and table name.');
    }
    if (table.dimensions.length === 0 && table.measures.length === 0) {
      throw new Error(`Table "${table.entityName}" must include at least one dimension or measure.`);
    }
  });
}

function serializeBuilderModel(builder: BuilderModel, connectorName?: string): string {
  const payload = buildSemanticModelPayload(builder, connectorName);
  return yaml.dump(payload, { noRefs: true, sortKeys: false });
}

function buildSemanticModelPayload(builder: BuilderModel, connectorName?: string) {
  const tables = builder.tables
    .filter(tableHasContent)
    .reduce<Record<string, unknown>>((acc, table) => {
      if (!table.entityName.trim() || !table.schema.trim() || !table.name.trim()) {
        return acc;
      }
      acc[table.entityName] = {
        schema: table.schema,
        name: table.name,
        description: table.description || undefined,
        dimensions:
          table.dimensions.length > 0
            ? table.dimensions
                .filter((dimension) => dimension.name && dimension.type)
                .map((dimension) => ({
                  name: dimension.name,
                  type: dimension.type,
                  description: dimension.description || undefined,
                  primary_key: dimension.primaryKey || undefined,
                  synonyms: dimension.synonyms && dimension.synonyms.length > 0 ? dimension.synonyms : undefined,
                  vectorized: dimension.vectorized ? true : undefined,
                }))
            : undefined,
        measures:
          table.measures.length > 0
            ? table.measures
                .filter((measure) => measure.name && measure.type)
                .map((measure) => ({
                  name: measure.name,
                  type: measure.type,
                  aggregation: measure.aggregation || undefined,
                  description: measure.description || undefined,
                  synonyms: measure.synonyms && measure.synonyms.length > 0 ? measure.synonyms : undefined,
                }))
            : undefined,
      };
      return acc;
    }, {});

  const relationships = builder.relationships
    .filter((relationship) => relationship.name && relationship.from && relationship.to && relationship.joinOn)
    .map((relationship) => ({
      name: relationship.name,
      from_: relationship.from,
      to: relationship.to,
      type: relationship.type,
      join_on: relationship.joinOn,
    }));

  const metrics = builder.metrics.reduce<Record<string, { expression: string; description?: string }>>(
    (acc, metric) => {
      if (!metric.name || !metric.expression) {
        return acc;
      }
      acc[metric.name] = {
        expression: metric.expression,
        description: metric.description || undefined,
      };
      return acc;
    },
    {},
  );

  return {
    version: builder.version || DEFAULT_MODEL_VERSION,
    connector: connectorName,
    description: builder.description || undefined,
    tables,
    relationships: relationships.length > 0 ? relationships : undefined,
    metrics: Object.keys(metrics).length > 0 ? metrics : undefined,
  };
}

function parseYamlToBuilderModel(yamlText: string): BuilderModel {
  const parsed = yaml.load(yamlText);
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Generated YAML was empty.');
  }

  const candidate = parsed as Record<string, any>;
  const tablesEntries = Object.entries((candidate.tables ?? {}) as Record<string, any>);
  const tables: BuilderTable[] = tablesEntries.map(([entityName, rawTable], index) => {
    const table = rawTable ?? {};
    const dimensions = Array.isArray(table.dimensions) ? table.dimensions : [];
    const measures = Array.isArray(table.measures) ? table.measures : [];
    return {
      id: createId('table'),
      entityName,
      schema: table.schema ?? '',
      name: table.name ?? '',
      description: table.description ?? '',
      synonyms: table.synonyms ?? null,
      filters: table.filters ?? null,
      dimensions: dimensions.map((dimension: any) => ({
        id: createId('dimension'),
        name: dimension.name ?? '',
        type: dimension.type ?? '',
        description: dimension.description ?? '',
        primaryKey: Boolean(dimension.primary_key ?? dimension.primaryKey),
        vectorized: Boolean(dimension.vectorized),
      })),
      measures: measures.map((measure: any) => ({
        id: createId('measure'),
        name: measure.name ?? '',
        type: measure.type ?? '',
        description: measure.description ?? '',
        aggregation: measure.aggregation ?? '',
      })),
    };
  });

  const relationshipSource = Array.isArray(candidate.relationships)
    ? candidate.relationships
    : Array.isArray(candidate.joins)
      ? candidate.joins
      : [];

  const relationships: BuilderRelationship[] = relationshipSource.map((relationship: any) => {
    const candidateType =
      (relationship.type as RelationshipType | undefined) ??
      (relationship.cardinality as RelationshipType | undefined);
    const resolvedType = candidateType && RELATIONSHIP_TYPES.includes(candidateType) ? candidateType : 'many_to_one';
    return {
      id: createId('relationship'),
      name: relationship.name ?? '',
      from: relationship.from_ ?? relationship.from ?? relationship.left ?? '',
      to: relationship.to ?? relationship.right ?? '',
      type: resolvedType,
      joinOn: relationship.join_on ?? relationship.joinOn ?? relationship.on ?? '',
    };
  });

  const metricsEntries = candidate.metrics ?? {};
  const metrics: BuilderMetric[] = Object.entries(metricsEntries as Record<string, any>).map(([metricName, metric]) => ({
    id: createId('metric'),
    name: metricName,
    expression: metric.expression ?? '',
    description: metric.description ?? '',
  }));

  return {
    version: typeof candidate.version === 'string' ? candidate.version : DEFAULT_MODEL_VERSION,
    description: candidate.description ?? '',
    tables,
    relationships,
    metrics,
  };
}
