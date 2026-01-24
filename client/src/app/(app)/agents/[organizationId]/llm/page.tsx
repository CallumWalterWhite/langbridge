'use client';

import { JSX, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Bot, Plus, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { formatRelativeDate } from '@/lib/utils';
import { fetchLLMConnections } from '@/orchestration/agents';
import type { LLMConnection } from '@/orchestration/agents';

type LLMConnectionsPageProps = {
  params: { organizationId: string };
};

export default function LLMConnectionsIndex({ params }: LLMConnectionsPageProps): JSX.Element {
  const router = useRouter();
  const { toast } = useToast();
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  const connectionsQuery = useQuery<LLMConnection[]>({
    queryKey: ['llm-connections', organizationId],
    queryFn: () => fetchLLMConnections(organizationId),
  });

  const connections = (connectionsQuery.data ?? [])
    .slice()
    .sort((a, b) => {
      const left = a.updatedAt ?? a.createdAt ?? '';
      const right = b.updatedAt ?? b.createdAt ?? '';
      if (left < right) {
        return 1;
      }
      if (left > right) {
        return -1;
      }
      return 0;
    });

  const handleCreate = () => {
    if (!organizationId) {
      toast({
        title: 'Select an organization',
        description: 'Choose a workspace scope before creating a connection.',
        variant: 'destructive',
      });
      return;
    }
    router.push(`/agents/${organizationId}/llm/create`);
  };

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              LLM connections
            </p>
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
                Manage provider credentials
              </h1>
              <p className="text-sm md:text-base">
                Keep Anthropic, OpenAI, and Azure keys in sync. Open a connection to rotate secrets or update model
                defaults.
              </p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-end">
            <Button onClick={handleCreate} size="sm" className="gap-2">
              <Plus className="h-4 w-4" aria-hidden="true" />
              New LLM connection
            </Button>
          </div>
        </div>
      </header>

      <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Connections</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => connectionsQuery.refetch()}
            disabled={connectionsQuery.isFetching}
            className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
          >
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
          </Button>
        </div>

        <div className="mt-6 flex-1">
          {connectionsQuery.isLoading ? (
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
          ) : connectionsQuery.isError ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <p className="text-sm">We couldn&apos;t load LLM connections right now.</p>
              <Button onClick={() => connectionsQuery.refetch()} variant="outline" size="sm">
                Try again
              </Button>
            </div>
          ) : connections.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                No connections yet
              </div>
              <div className="space-y-2">
                <p className="text-base font-semibold text-[color:var(--text-primary)]">No LLM credentials found</p>
                <p className="text-sm">Register your first provider key to start orchestrating agents.</p>
              </div>
              <Button onClick={handleCreate} size="sm" className="gap-2">
                <Plus className="h-4 w-4" aria-hidden="true" />
                Create connection
              </Button>
            </div>
          ) : (
            <ul className="space-y-3">
              {connections.map((connection) => (
                <li key={connection.id}>
                  <Link
                    href={`/agents/${organizationId}/llm/${connection.id}`}
                    className="group flex items-center justify-between rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-4 transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-alt)]"
                  >
                    <div className="flex items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-sm font-semibold text-[color:var(--text-primary)]">
                        <Bot className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-[color:var(--text-primary)]">{connection.name}</p>
                        <p className="text-xs text-[color:var(--text-muted)]">
                          {connection.provider.toUpperCase()} - Model {connection.model}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[color:var(--text-muted)]">
                      <span>
                        Updated {formatRelativeDate(connection.updatedAt ?? connection.createdAt ?? new Date().toISOString())}
                      </span>
                      <ArrowRight
                        className="h-4 w-4 text-[color:var(--text-muted)] transition group-hover:translate-x-1 group-hover:text-[color:var(--text-primary)]"
                        aria-hidden="true"
                      />
                    </div>
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
