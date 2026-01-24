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
import { fetchConnectors } from '@/orchestration/connectors';
import type { ConnectorResponse } from '@/orchestration/connectors/types';
import { createSemanticModel, listSemanticModels } from '@/orchestration/semanticModels';
import type { SemanticModelRecord } from '@/orchestration/semanticModels/types';
import { ApiError } from '@/orchestration/http';
import { cn, formatRelativeDate } from '@/lib/utils';

type JoinType = 'inner' | 'left' | 'right' | 'full';

interface FormState {
  name: string;
  description: string;
  version: string;
}

interface BuilderRelationship {
  id: string;
  name: string;
  from: string;
  to: string;
  on: string;
  type: JoinType;
}

interface UnifiedMetric {
  id: string;
  name: string;
  expression: string;
  description?: string;
}

const DEFAULT_VERSION = '1.0';
const JOIN_TYPES: JoinType[] = ['inner', 'left', 'right', 'full'];

type UnifiedSemanticModelPageProps = {
  params: { organizationId: string };
};

export default function UnifiedSemanticModelPage({ params }: UnifiedSemanticModelPageProps): JSX.Element {
  const {
    selectedOrganizationId,
    selectedProjectId,
    organizations,
    loading: scopeLoading,
    setSelectedOrganizationId,
  } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  const [connectors, setConnectors] = useState<ConnectorResponse[]>([]);
  const [connectorsLoading, setConnectorsLoading] = useState(false);
  const [semanticModels, setSemanticModels] = useState<SemanticModelRecord[]>([]);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [selectedConnectorId, setSelectedConnectorId] = useState('');
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  const [relationships, setRelationships] = useState<BuilderRelationship[]>([]);
  const [metrics, setMetrics] = useState<UnifiedMetric[]>([]);
  const [formState, setFormState] = useState<FormState>({ name: '', description: '', version: DEFAULT_VERSION });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedConnector = useMemo(
    () => connectors.find((connector) => connector.id === selectedConnectorId),
    [connectors, selectedConnectorId],
  );

  const selectedModels = useMemo(
    () => semanticModels.filter((model) => selectedModelIds.includes(model.id)),
    [semanticModels, selectedModelIds],
  );

  const organizationName = useMemo(() => {
    if (!organizationId) {
      return 'Select an organization';
    }
    return organizations.find((org) => org.id === organizationId)?.name ?? 'Unknown organization';
  }, [organizations, organizationId]);

  const unifiedYamlPreview = useMemo(() => {
    try {
      const payload = buildUnifiedPayload({
        formState,
        selectedModels,
        relationships,
        metrics,
        connectorName: selectedConnector?.name,
      });
      const yamlText = yaml.dump(payload, { noRefs: true, sortKeys: false });
      return { yaml: yamlText, error: null };
    } catch (err) {
      return {
        yaml: '',
        error: err instanceof Error ? err.message : 'Unable to build unified model YAML.',
      };
    }
  }, [formState, selectedModels, relationships, metrics, selectedConnector?.name]);

  const loadConnectors = useCallback(async () => {
    if (!organizationId) {
      setConnectors([]);
      setSelectedConnectorId('');
      return;
    }
    setConnectorsLoading(true);
    try {
      const data = await fetchConnectors(organizationId);
      setConnectors(data);
      setSelectedConnectorId((current) => {
        if (current) {
          return current;
        }
        const trino = data.find((connector) => connector.connectorType?.toLowerCase() === 'trino');
        if (trino?.id) {
          return trino.id;
        }
        const first = data.find((connector) => connector.id);
        return first?.id ?? '';
      });
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setConnectorsLoading(false);
    }
  }, [organizationId]);

  const loadSemanticModels = useCallback(async () => {
    if (!organizationId) {
      setSemanticModels([]);
      return;
    }
    setSemanticLoading(true);
    try {
      const models = await listSemanticModels(organizationId, selectedProjectId ?? undefined);
      setSemanticModels(models);
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSemanticLoading(false);
    }
  }, [organizationId, selectedProjectId]);

  useEffect(() => {
    if (!organizationId) {
      setConnectors([]);
      setSemanticModels([]);
      setSelectedModelIds([]);
      setSelectedConnectorId('');
      return;
    }
    void loadConnectors();
    void loadSemanticModels();
  }, [organizationId, loadConnectors, loadSemanticModels]);

  useEffect(() => {
    setSelectedModelIds([]);
    setRelationships([]);
    setMetrics([]);
  }, [selectedConnectorId]);

  const toggleModelSelection = (modelId: string) => {
    setSelectedModelIds((current) =>
      current.includes(modelId) ? current.filter((id) => id !== modelId) : [...current, modelId],
    );
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!organizationId) {
      setError('Select an organization before saving.');
      return;
    }
    if (!selectedConnectorId) {
      setError('Select a connector to run unified queries through (Trino recommended).');
      return;
    }
    if (selectedModelIds.length === 0) {
      setError('Choose at least one semantic model to compose.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const payload = buildUnifiedPayload({
        formState,
        selectedModels,
        relationships,
        metrics,
        connectorName: selectedConnector?.name,
      });
      const yamlText = yaml.dump(payload, { noRefs: true, sortKeys: false });
      await createSemanticModel(organizationId, {
        organizationId,
        projectId: selectedProjectId ?? undefined,
        connectorId: selectedConnectorId,
        name: formState.name || payload.name,
        description: formState.description || undefined,
        modelYaml: yamlText,
        autoGenerate: false,
      });
      await loadSemanticModels();
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[color:var(--text-muted)]">
          Unified semantic models
        </p>
        <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
          Compose and query across semantic models
        </h1>
        <p className="max-w-3xl text-sm">
          Pick a Trino connector, select the semantic models you want to stitch together, define cross-model joins and
          shared metrics, and save a single YAML artifact for agents to route unified questions.
        </p>
        <p className="text-xs text-[color:var(--text-muted)]">
          Scope: <span className="font-medium text-[color:var(--text-primary)]">{organizationName}</span>
          {selectedProjectId ? ' - project scoped' : ' - organization scoped'}
        </p>
      </header>

      {error ? (
        <div className="rounded-lg border border-rose-300 bg-rose-100/40 px-4 py-3 text-sm text-rose-700">{error}</div>
      ) : null}

      {!organizationId && !scopeLoading ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-center text-sm">
          Choose an organization from the scope selector to begin.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <section className="space-y-6 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
            <form className="space-y-6" onSubmit={(event) => void handleSubmit(event)}>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">1. Select a connector</h2>
                  <Button type="button" variant="outline" size="sm" onClick={() => void loadConnectors()} isLoading={connectorsLoading}>
                    Refresh
                  </Button>
                </div>
                <p className="text-sm">
                  Unified models execute through Trino. Pick a Trino connector for best compatibility; other SQL
                  connectors are shown if available.
                </p>
                {connectors.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-6 text-sm">
                    No connectors available. Create a connector first.
                  </div>
                ) : (
                  <div className="grid gap-3 md:grid-cols-2">
                    {connectors.map((connector) => {
                      const connectorId = connector.id ?? '';
                      const isSelected = connectorId === selectedConnectorId;
                      const isTrino = connector.connectorType?.toLowerCase() === 'trino';
                      return (
                        <button
                          key={connector.id ?? connector.name}
                          type="button"
                          onClick={() => setSelectedConnectorId(connectorId)}
                          disabled={!connectorId}
                          className={cn(
                            'rounded-2xl border bg-[color:var(--panel-alt)] p-4 text-left transition hover:border-[color:var(--border-strong)]',
                            isSelected ? 'border-[color:var(--accent)] shadow-soft' : 'border-[color:var(--panel-border)]',
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-[color:var(--text-primary)]">{connector.name}</p>
                              <p className="text-xs text-[color:var(--text-muted)]">
                                {connector.description ?? 'No description provided.'}
                              </p>
                            </div>
                            {isSelected ? <Badge variant="secondary">Selected</Badge> : null}
                          </div>
                          <div className="mt-2 flex items-center gap-2 text-xs text-[color:var(--text-muted)]">
                            <span className="rounded-full border border-[color:var(--panel-border)] px-2 py-0.5">
                              {connector.connectorType ?? 'Custom'}
                            </span>
                            {isTrino ? (
                              <span className="rounded-full border border-[color:var(--accent)] px-2 py-0.5 text-[color:var(--accent)]">
                                Trino recommended
                              </span>
                            ) : null}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {!selectedConnectorId ? (
                <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-6 text-sm">
                  Select a connector to unlock the unified builder.
                </div>
              ) : (
                <>
                  <div className="space-y-4 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h3 className="text-base font-semibold text-[color:var(--text-primary)]">2. Metadata</h3>
                        <p className="text-xs text-[color:var(--text-muted)]">
                          Name and describe the unified layer; version is tracked in the YAML.
                        </p>
                      </div>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="unified-name">Unified model name</Label>
                        <Input
                          id="unified-name"
                          value={formState.name}
                          onChange={(event) => setFormState((current) => ({ ...current, name: event.target.value }))}
                          placeholder="e.g. Revenue intelligence hub"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="unified-version">Version</Label>
                        <Input
                          id="unified-version"
                          value={formState.version}
                          onChange={(event) =>
                            setFormState((current) => ({ ...current, version: event.target.value || DEFAULT_VERSION }))
                          }
                        />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="unified-description">Description</Label>
                      <Textarea
                        id="unified-description"
                        rows={3}
                        value={formState.description}
                        onChange={(event) =>
                          setFormState((current) => ({ ...current, description: event.target.value }))
                        }
                        placeholder="What problems does this unified layer solve?"
                      />
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-semibold text-[color:var(--text-primary)]">3. Choose models</h3>
                      <Badge variant="secondary">{semanticModels.length}</Badge>
                    </div>
                    {semanticLoading ? (
                      <p className="text-sm">Loading semantic models...</p>
                    ) : semanticModels.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-6 text-sm">
                        No semantic models found in this scope. Create at least one before unifying.
                      </div>
                    ) : (
                      <div className="grid gap-3 md:grid-cols-2">
                        {semanticModels.map((model) => {
                          const isSelected = selectedModelIds.includes(model.id);
                          return (
                            <button
                              key={model.id}
                              type="button"
                              onClick={() => toggleModelSelection(model.id)}
                              className={cn(
                                'rounded-2xl border bg-[color:var(--panel-alt)] p-4 text-left transition hover:border-[color:var(--border-strong)]',
                                isSelected ? 'border-[color:var(--accent)] shadow-soft' : 'border-[color:var(--panel-border)]',
                              )}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-semibold text-[color:var(--text-primary)]">{model.name}</p>
                                  <p className="text-xs text-[color:var(--text-muted)]">
                                    Updated {formatRelativeDate(model.updatedAt)}
                                  </p>
                                  {model.description ? (
                                    <p className="mt-2 text-xs text-[color:var(--text-secondary)]">{model.description}</p>
                                  ) : null}
                                </div>
                                {isSelected ? <Badge variant="secondary">Added</Badge> : null}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-semibold text-[color:var(--text-primary)]">4. Cross-model relationships</h3>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setRelationships((current) => [
                            ...current,
                            {
                              id: createId('relationship'),
                              name: `relationship_${current.length + 1}`,
                              from: '',
                              to: '',
                              on: '',
                              type: 'inner',
                            },
                          ])
                        }
                      >
                        Add relationship
                      </Button>
                    </div>
                    {relationships.length === 0 ? (
                      <p className="text-sm text-[color:var(--text-muted)]">
                        No relationships yet. Add joins to link tables across models.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {relationships.map((relationship) => (
                          <div
                            key={relationship.id}
                            className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div className="space-y-1">
                                <Label htmlFor={`rel-name-${relationship.id}`}>Name</Label>
                                <Input
                                  id={`rel-name-${relationship.id}`}
                                  value={relationship.name}
                                  onChange={(event) =>
                                    setRelationships((current) =>
                                      current.map((entry) =>
                                        entry.id === relationship.id ? { ...entry, name: event.target.value } : entry,
                                      ),
                                    )
                                  }
                                  placeholder="orders_to_customers"
                                />
                              </div>
                              <div className="space-y-1">
                                <Label htmlFor={`rel-type-${relationship.id}`}>Join type</Label>
                                <Select
                                  id={`rel-type-${relationship.id}`}
                                  value={relationship.type}
                                  onChange={(event) =>
                                    setRelationships((current) =>
                                      current.map((entry) =>
                                        entry.id === relationship.id
                                          ? { ...entry, type: event.target.value as JoinType }
                                          : entry,
                                      ),
                                    )
                                  }
                                >
                                  {JOIN_TYPES.map((type) => (
                                    <option key={type} value={type}>
                                      {type}
                                    </option>
                                  ))}
                                </Select>
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  setRelationships((current) => current.filter((entry) => entry.id !== relationship.id))
                                }
                              >
                                Remove
                              </Button>
                            </div>
                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="space-y-1">
                                <Label htmlFor={`rel-from-${relationship.id}`}>From</Label>
                                <Input
                                  id={`rel-from-${relationship.id}`}
                                  value={relationship.from}
                                  onChange={(event) =>
                                    setRelationships((current) =>
                                      current.map((entry) =>
                                        entry.id === relationship.id ? { ...entry, from: event.target.value } : entry,
                                      ),
                                    )
                                  }
                                  placeholder="orders.orders"
                                />
                              </div>
                              <div className="space-y-1">
                                <Label htmlFor={`rel-to-${relationship.id}`}>To</Label>
                                <Input
                                  id={`rel-to-${relationship.id}`}
                                  value={relationship.to}
                                  onChange={(event) =>
                                    setRelationships((current) =>
                                      current.map((entry) =>
                                        entry.id === relationship.id ? { ...entry, to: event.target.value } : entry,
                                      ),
                                    )
                                  }
                                  placeholder="customers.customers"
                                />
                              </div>
                            </div>
                            <div className="space-y-1">
                              <Label htmlFor={`rel-on-${relationship.id}`}>Join condition</Label>
                              <Textarea
                                id={`rel-on-${relationship.id}`}
                                rows={2}
                                value={relationship.on}
                                onChange={(event) =>
                                  setRelationships((current) =>
                                    current.map((entry) =>
                                      entry.id === relationship.id ? { ...entry, on: event.target.value } : entry,
                                    ),
                                  )
                                }
                                placeholder="orders.orders.customer_id = customers.customers.id"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-semibold text-[color:var(--text-primary)]">5. Unified metrics</h3>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setMetrics((current) => [
                            ...current,
                            { id: createId('metric'), name: '', expression: '', description: '' },
                          ])
                        }
                      >
                        Add metric
                      </Button>
                    </div>
                    {metrics.length === 0 ? (
                      <p className="text-sm text-[color:var(--text-muted)]">
                        No unified metrics yet. Add shared definitions that leverage multiple models.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {metrics.map((metric) => (
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
                                onClick={() => setMetrics((current) => current.filter((entry) => entry.id !== metric.id))}
                              >
                                Remove
                              </Button>
                            </div>
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              <Input
                                value={metric.name}
                                onChange={(event) =>
                                  setMetrics((current) =>
                                    current.map((entry) =>
                                      entry.id === metric.id ? { ...entry, name: event.target.value } : entry,
                                    ),
                                  )
                                }
                                placeholder="metric name"
                              />
                              <Input
                                value={metric.description ?? ''}
                                onChange={(event) =>
                                  setMetrics((current) =>
                                    current.map((entry) =>
                                      entry.id === metric.id ? { ...entry, description: event.target.value } : entry,
                                    ),
                                  )
                                }
                                placeholder="description"
                              />
                            </div>
                            <Textarea
                              className="mt-3"
                              rows={3}
                              value={metric.expression}
                              onChange={(event) =>
                                setMetrics((current) =>
                                  current.map((entry) =>
                                    entry.id === metric.id ? { ...entry, expression: event.target.value } : entry,
                                  ),
                                )
                              }
                              placeholder="SQL expression referencing entities across models"
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-semibold text-[color:var(--text-primary)]">6. YAML preview</h3>
                      <span className="text-xs text-[color:var(--text-muted)]">The payload saved to the API</span>
                    </div>
                    {unifiedYamlPreview.error ? (
                      <p className="text-xs text-rose-600">{unifiedYamlPreview.error}</p>
                    ) : null}
                    <Textarea
                      readOnly
                      rows={12}
                      value={unifiedYamlPreview.yaml}
                      className="font-mono text-xs"
                      placeholder="YAML will appear once models are selected."
                    />
                    <Button type="submit" className="w-full" disabled={submitting} isLoading={submitting}>
                      Save unified model
                    </Button>
                  </div>
                </>
              )}
            </form>
          </section>

          <aside className="space-y-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">Selected models</h2>
              <Badge variant="secondary">{selectedModels.length}</Badge>
            </div>
            {selectedModels.length === 0 ? (
              <p className="text-sm text-[color:var(--text-muted)]">Pick semantic models to stitch together.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {selectedModels.map((model) => (
                  <li
                    key={model.id}
                    className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-[color:var(--text-primary)]">{model.name}</p>
                        <p className="text-xs text-[color:var(--text-muted)]">Updated {formatRelativeDate(model.updatedAt)}</p>
                        {model.description ? (
                          <p className="mt-2 text-xs text-[color:var(--text-secondary)]">{model.description}</p>
                        ) : null}
                      </div>
                      <Button type="button" size="sm" variant="ghost" onClick={() => toggleModelSelection(model.id)}>
                        Remove
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-xs text-[color:var(--text-muted)]">
              Builder tips:
              <ul className="mt-2 list-disc space-y-1 pl-4">
                <li>Use fully qualified entity names in joins (entity.column).</li>
                <li>Unified metrics can reference columns across the selected models.</li>
                <li>
                  The saved YAML is compatible with the SQL analyst tool; agents will automatically route cross-model
                  questions here.
                </li>
              </ul>
            </div>
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

function buildUnifiedPayload({
  formState,
  selectedModels,
  relationships,
  metrics,
  connectorName,
}: {
  formState: FormState;
  selectedModels: SemanticModelRecord[];
  relationships: BuilderRelationship[];
  metrics: UnifiedMetric[];
  connectorName?: string;
}) {
  if (selectedModels.length === 0) {
    throw new Error('Select at least one semantic model to compose.');
  }

  const parsedModels = selectedModels.map((model, index) => {
    const parsed = yaml.load(model.contentYaml ?? '') as Record<string, any> | undefined;
    if (!parsed || typeof parsed !== 'object') {
      throw new Error(`Semantic model "${model.name}" is missing YAML content.`);
    }
    const fallbackName = (parsed as Record<string, any>).name ?? model.name ?? `model_${index + 1}`;
    return { name: fallbackName, ...parsed };
  });

  const rels = relationships
    .filter((relationship) => relationship.from && relationship.to && relationship.on)
    .map((relationship) => ({
      name: relationship.name,
      from: relationship.from,
      to: relationship.to,
      type: relationship.type,
      on: relationship.on,
    }));

  const metricMap = metrics.reduce<Record<string, { expression: string; description?: string }>>((acc, metric) => {
    if (!metric.name || !metric.expression) {
      return acc;
    }
    acc[metric.name] = {
      expression: metric.expression,
      description: metric.description || undefined,
    };
    return acc;
  }, {});

  const name = formState.name || parsedModels[0].name || 'unified_model';

  return {
    name,
    version: formState.version || DEFAULT_VERSION,
    connector: connectorName,
    dialect: 'trino',
    description: formState.description || undefined,
    semantic_models: parsedModels,
    relationships: rels.length > 0 ? rels : undefined,
    metrics: Object.keys(metricMap).length > 0 ? metricMap : undefined,
  };
}



