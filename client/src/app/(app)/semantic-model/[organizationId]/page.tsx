'use client';

import { JSX, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Layers3, Plus, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { formatRelativeDate } from '@/lib/utils';
import { listSemanticModels } from '@/orchestration/semanticModels';
import type { SemanticModelRecord } from '@/orchestration/semanticModels/types';

const semanticModelsQueryKey = (organizationId: string, projectId: string | null | undefined) =>
  ['semantic-models', organizationId, projectId] as const;

type SemanticModelsIndexProps = {
  params: { organizationId: string };
};

export default function SemanticModelsIndex({ params }: SemanticModelsIndexProps): JSX.Element {
  const router = useRouter();
  const { selectedOrganizationId, selectedProjectId, setSelectedOrganizationId } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  const hasOrganization = Boolean(organizationId);

  const semanticModelsQuery = useQuery<SemanticModelRecord[]>({
    queryKey: semanticModelsQueryKey(organizationId, selectedProjectId),
    queryFn: () => listSemanticModels(organizationId, selectedProjectId ?? undefined, 'standard'),
    enabled: hasOrganization,
  });

  const models = (semanticModelsQuery.data ?? [])
    .slice()
    .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));

  const handleCreate = () => {
    router.push(`/semantic-model/${organizationId}/create`);
  };

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              Semantic models
            </p>
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
                Curate semantic layers
              </h1>
              <p className="text-sm md:text-base">
                Track generated models and make targeted edits before publishing to the LangBridge orchestration layer.
              </p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-end">
            <Button onClick={handleCreate} size="sm" className="gap-2">
              <Plus className="h-4 w-4" aria-hidden="true" />
              New semantic model
            </Button>
          </div>
        </div>
      </header>

      <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Models</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => semanticModelsQuery.refetch()}
            disabled={semanticModelsQuery.isFetching || !hasOrganization}
            className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
          >
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
          </Button>
        </div>

        <div className="mt-6 flex-1">
          {!hasOrganization ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-[color:var(--text-muted)]">
              <p className="text-sm">Select an organization to view its semantic models.</p>
              <p className="text-xs">Once a scope is active, generated models will be listed here.</p>
            </div>
          ) : semanticModelsQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                >
                  <Skeleton className="h-4 w-32" />
                </div>
              ))}
            </div>
          ) : semanticModelsQuery.isError ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <p className="text-sm">We couldn&apos;t load semantic models right now.</p>
              <Button onClick={() => semanticModelsQuery.refetch()} variant="outline" size="sm">
                Try again
              </Button>
            </div>
          ) : models.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                No models yet
              </div>
              <div className="space-y-2">
                <p className="text-base font-semibold text-[color:var(--text-primary)]">No semantic models found</p>
                <p className="text-sm">Auto-generate the first version to expose tables, metrics, and relationships.</p>
              </div>
              <Button onClick={handleCreate} size="sm" className="gap-2">
                <Plus className="h-4 w-4" aria-hidden="true" />
                Create model
              </Button>
            </div>
          ) : (
            <ul className="space-y-3">
              {models.map((model) => (
                <li key={model.id}>
                  <Link
                    href={`/semantic-model/${organizationId}/create?modelId=${model.id}`}
                    className="group flex items-center justify-between rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-4 transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-alt)]"
                  >
                    <div className="flex items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-sm font-semibold text-[color:var(--text-primary)]">
                        <Layers3 className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-[color:var(--text-primary)]">{model.name}</p>
                        <p className="text-xs text-[color:var(--text-muted)]">
                          Updated {formatRelativeDate(model.updatedAt)}
                          {model.description ? ` - ${model.description}` : ''}
                        </p>
                      </div>
                    </div>
                    <ArrowRight
                      className="h-4 w-4 text-[color:var(--text-muted)] transition group-hover:translate-x-1 group-hover:text-[color:var(--text-primary)]"
                      aria-hidden="true"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
