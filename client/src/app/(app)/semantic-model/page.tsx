'use client';

import { JSX, useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useWorkspaceScope } from '@/context/workspaceScope';
import {
  createSemanticModel,
  deleteSemanticModel,
  fetchSemanticModelYaml,
  listSemanticModels,
  previewSemanticModel,
} from '@/orchestration/semanticModels';
import {
  fetchConnectors
} from '@/orchestration/connectors';
import type {
  ConnectorResponse,
} from '@/orchestration/connectors/types';
import type {
  SemanticModel,
  SemanticModelRecord,
} from '@/orchestration/semanticModels/types';
import { ApiError } from '@/orchestration/http';
import { formatRelativeDate } from '@/lib/utils';

interface FormState {
  name: string;
  description: string;
}

export default function SemanticModelPage(): JSX.Element {
  const {
    selectedOrganizationId,
    selectedProjectId,
    organizations,
    loading: scopeLoading,
  } = useWorkspaceScope();

  const [preview, setPreview] = useState<SemanticModel | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [storedModels, setStoredModels] = useState<SemanticModelRecord[]>([]);
  const [storedLoading, setStoredLoading] = useState(false);
  const [formState, setFormState] = useState<FormState>({ name: '', description: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);
  const [connectors, setConnectors] = useState<ConnectorResponse[]>([]);

  const organizationAvailable = Boolean(selectedOrganizationId);

  const currentOrganizationName = useMemo(() => {
    if (!selectedOrganizationId) {
      return 'Select an organization';
    }
    return (
      organizations.find((org) => org.id === selectedOrganizationId)?.name ?? 'Unknown organization'
    );
  }, [organizations, selectedOrganizationId]);

  const loadConnectors = useCallback(async () => {
    if (!selectedOrganizationId) {
      return;
    }
    try {
      const data = await fetchConnectors(selectedOrganizationId);
      setConnectors(data);
    } catch (err) {
      // Handle error silently for connectors loading
    }
  }, [selectedOrganizationId]);

  const refreshPreview = useCallback(async () => {
    if (!selectedOrganizationId) {
      return;
    }
    setPreviewLoading(true);
    setError(null);
    try {
      const data = await previewSemanticModel(selectedOrganizationId, selectedProjectId ?? undefined);
      setPreview(data);
    } catch (err) {
      setError(resolveError(err));
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [selectedOrganizationId, selectedProjectId]);

  const refreshStoredModels = useCallback(async () => {
    if (!selectedOrganizationId) {
      return;
    }
    setStoredLoading(true);
    try {
      const list = await listSemanticModels(selectedOrganizationId, selectedProjectId ?? undefined);
      setStoredModels(list);
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setStoredLoading(false);
    }
  }, [selectedOrganizationId, selectedProjectId]);

  useEffect(() => {
    if (!selectedOrganizationId) {
      setPreview(null);
      setStoredModels([]);
      return;
    }
    void refreshPreview();
    void refreshStoredModels();
  }, [selectedOrganizationId, selectedProjectId, refreshPreview, refreshStoredModels]);

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) {
      setError('Select an organization before saving a semantic model.');
      return;
    }
    if (!formState.name.trim()) {
      setError('Provide a name for the semantic model.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await createSemanticModel({
        organizationId: selectedOrganizationId,
        projectId: selectedProjectId ?? undefined,
        name: formState.name.trim(),
        description: formState.description.trim() || undefined,
        autoGenerate: true,
      });
      setFormState({ name: '', description: '' });
      await refreshStoredModels();
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSubmitting(false);
    }
  }

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

  useEffect(() => {
    setIsClient(true);
  }, []);

  const tables = useMemo(() => Object.entries(preview?.tables ?? {}), [preview]);

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-[color:var(--text-primary)]">Semantic model builder</h1>
        <p className="max-w-3xl text-sm">
          Generate a unified semantic layer over your LangBridge connectors. The preview aggregates metadata from your
          active connectors so agents can reason across shared dimensions and measures.
        </p>
        <div className="text-xs text-[color:var(--text-muted)]">
          Scope: <span className="font-medium text-[color:var(--text-primary)]">{currentOrganizationName}</span>
          {selectedProjectId ? ' - project scoped' : ' - organization scoped'}
        </div>
      </header>

      {error ? (
        <div className="rounded-lg border border-rose-300 bg-rose-100/40 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {!organizationAvailable && !scopeLoading ? (
        <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-center text-sm">
          Choose an organization from the scope selector to begin modeling.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">Preview model</h2>
              <Button variant="outline" size="sm" isLoading={previewLoading} onClick={() => void refreshPreview()}>
                Refresh preview
              </Button>
            </div>

            <div className="space-y-4">
              {previewLoading ? (
                <div className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-sm">
                  Generating semantic preview...
                </div>
              ) : tables.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-sm">
                  No tables discovered. Ensure your connectors are configured correctly.
                </div>
              ) : (
                tables.map(([tableName, table]) => (
                  <article
                    key={tableName}
                    className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft"
                  >
                    <header className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <h3 className="text-base font-semibold text-[color:var(--text-primary)]">{tableName}</h3>
                        {table.description ? (
                          <p className="text-xs text-[color:var(--text-muted)]">{table.description}</p>
                        ) : null}
                      </div>
                      <div className="flex gap-2 text-xs">
                        <Badge variant="secondary">{table.dimensions?.length ?? 0} dimensions</Badge>
                        <Badge variant="secondary">{table.measures?.length ?? 0} measures</Badge>
                      </div>
                    </header>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div>
                        <h4 className="text-sm font-semibold text-[color:var(--text-primary)]">Dimensions</h4>
                        <ul className="mt-2 space-y-2 text-sm">
                          {(table.dimensions ?? []).map((dimension) => (
                            <li key={dimension.name} className="rounded-lg border border-[color:var(--panel-border)] p-3">
                              <div className="flex items-center justify-between text-[color:var(--text-primary)]">
                                <span className="font-medium">{dimension.name}</span>
                                {dimension.primaryKey ? <Badge variant="secondary">PK</Badge> : null}
                              </div>
                              <p className="text-xs text-[color:var(--text-muted)]">Type: {dimension.type}</p>
                              {dimension.description ? (
                                <p className="mt-1 text-xs text-[color:var(--text-muted)]">{dimension.description}</p>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-[color:var(--text-primary)]">Measures</h4>
                        <ul className="mt-2 space-y-2 text-sm">
                          {(table.measures ?? []).map((measure) => (
                            <li key={measure.name} className="rounded-lg border border-[color:var(--panel-border)] p-3">
                              <div className="flex items-center justify-between text-[color:var(--text-primary)]">
                                <span className="font-medium">{measure.name}</span>
                                {measure.aggregation ? <Badge variant="secondary">{measure.aggregation}</Badge> : null}
                              </div>
                              <p className="text-xs text-[color:var(--text-muted)]">Type: {measure.type}</p>
                              {measure.description ? (
                                <p className="mt-1 text-xs text-[color:var(--text-muted)]">{measure.description}</p>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </article>
                ))
              )}
            </div>

            {preview?.relationships && preview.relationships.length > 0 ? (
              <section className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
                <h3 className="text-base font-semibold text-[color:var(--text-primary)]">Detected relationships</h3>
                <ul className="mt-3 space-y-3 text-sm">
                  {preview.relationships.map((relationship) => (
                    <li key={relationship.name} className="rounded-lg border border-[color:var(--panel-border)] p-3">
                      <div className="font-medium text-[color:var(--text-primary)]">{relationship.name}</div>
                      <p className="text-xs text-[color:var(--text-muted)]">Join: {relationship.joinOn}</p>
                      <p className="text-xs text-[color:var(--text-muted)]">Type: {relationship.type}</p>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </section>

          <aside className="space-y-6">
            <section className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
              <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">Save semantic model</h2>
              <p className="mt-1 text-sm">
                Give the generated model a name and description. We\u2019ll snapshot the YAML to reuse across agents and
                analytics experiences.
              </p>

              <form className="mt-4 space-y-4" onSubmit={handleSave}>
                <div className="space-y-2">
                  <Label htmlFor="model-name">Model name</Label>
                  <Input
                    id="model-name"
                    value={formState.name}
                    onChange={(event) => setFormState((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Customer 360 semantic model"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="model-description">Description</Label>
                  <Textarea
                    id="model-description"
                    value={formState.description}
                    onChange={(event) => setFormState((current) => ({ ...current, description: event.target.value }))}
                    placeholder="Outline what this semantic layer covers for downstream agents."
                  />
                </div>
                <Button type="submit" className="w-full" isLoading={submitting} disabled={!organizationAvailable}>
                  Save semantic model
                </Button>
              </form>
            </section>

            <section className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">Saved models</h2>
                <Badge variant="secondary">{storedModels.length}</Badge>
              </div>
              {storedLoading ? (
                <p className="mt-3 text-sm">Loading saved models...</p>
              ) : storedModels.length === 0 ? (
                <p className="mt-3 text-sm">No saved models yet. Generate and save one to reuse in agents.</p>
              ) : (
                <ul className="mt-4 space-y-3 text-sm">
                  {storedModels.map((model) => (
                    <li key={model.id} className="rounded-lg border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold text-[color:var(--text-primary)]">{model.name}</p>
                          <p className="text-xs text-[color:var(--text-muted)]">
                            Saved {isClient ? formatRelativeDate(model.updatedAt) : ""}
                          </p>
                          {model.description ? (
                            <p className="mt-2 text-xs text-[color:var(--text-secondary)]">{model.description}</p>
                          ) : null}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => void handleDownloadYaml(model.id, model.name)}
                          >
                            Download YAML
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => void handleDelete(model.id)}
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
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
