'use client';

import { JSX, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, Bot, Plus, RefreshCw, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { fetchAgentDefinitions, deleteAgentDefinition, fetchLLMConnections } from '@/orchestration/agents';
import type { AgentDefinition, LLMConnection } from '@/orchestration/agents';

type AgentDefinitionsPageProps = {
  params: { organizationId: string };
};

export default function AgentDefinitionsPage({ params }: AgentDefinitionsPageProps): JSX.Element {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  const definitionsQuery = useQuery<AgentDefinition[]>({
    queryKey: ['agent-definitions', organizationId],
    queryFn: () => fetchAgentDefinitions(organizationId),
  });

  const connectionsQuery = useQuery<LLMConnection[]>({
    queryKey: ['llm-connections', organizationId],
    queryFn: () => fetchLLMConnections(organizationId),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAgentDefinition(organizationId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-definitions', organizationId] });
      toast({ title: 'Agent deleted' });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Unable to delete agent right now.';
      toast({ title: 'Delete failed', description: message, variant: 'destructive' });
    },
  });

  const connectionLookup = useMemo(() => {
    return Object.fromEntries((connectionsQuery.data ?? []).map((conn) => [conn.id, conn.name]));
  }, [connectionsQuery.data]);

  const definitions = (definitionsQuery.data ?? []).slice().sort((a, b) => {
    const left = a.updatedAt ?? a.createdAt ?? '';
    const right = b.updatedAt ?? b.createdAt ?? '';
    return left < right ? 1 : left > right ? -1 : 0;
  });

  const handleDelete = (id: string) => {
    if (deleteMutation.isPending) return;
    const confirmed = window.confirm('Delete this agent definition?');
    if (!confirmed) return;
    deleteMutation.mutate(id);
  };

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Agents</p>
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">Agent definitions</h1>
              <p className="text-sm md:text-base">Build prompts, memory, guardrails, and tool wiring for each agent.</p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-end">
            <Button onClick={() => router.push(`/agents/${organizationId}/definitions/create`)} size="sm" className="gap-2">
              <Plus className="h-4 w-4" aria-hidden="true" />
              New agent
            </Button>
          </div>
        </div>
      </header>

      <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Definitions</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              definitionsQuery.refetch();
              connectionsQuery.refetch();
            }}
            disabled={definitionsQuery.isFetching}
            className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
          >
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
          </Button>
        </div>

        <div className="mt-6 flex-1">
          {definitionsQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                >
                  <Skeleton className="h-4 w-48" />
                </div>
              ))}
            </div>
          ) : definitionsQuery.isError ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <p className="text-sm">We couldn&apos;t load agent definitions right now.</p>
              <Button onClick={() => definitionsQuery.refetch()} variant="outline" size="sm">
                Try again
              </Button>
            </div>
          ) : definitions.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                No agents yet
              </div>
              <div className="space-y-2">
                <p className="text-base font-semibold text-[color:var(--text-primary)]">Create your first agent</p>
                <p className="text-sm">Design prompts, memory, and guardrails for your workflows.</p>
              </div>
              <Button onClick={() => router.push(`/agents/${organizationId}/definitions/create`)} size="sm" className="gap-2">
                <Plus className="h-4 w-4" aria-hidden="true" />
                Build an agent
              </Button>
            </div>
          ) : (
            <ul className="space-y-3">
              {definitions.map((agent) => (
                <li key={agent.id} className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-1 items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-sm font-semibold text-[color:var(--text-primary)]">
                        <Bot className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-[color:var(--text-primary)]">{agent.name}</p>
                        <p className="text-xs text-[color:var(--text-muted)]">
                          {agent.description || 'No description provided'}
                        </p>
                        <p className="text-xs text-[color:var(--text-muted)]">
                          Connection: {connectionLookup[agent.llmConnectionId] ?? agent.llmConnectionId}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-[color:var(--text-muted)]">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => router.push(`/agents/${organizationId}/definitions/${agent.id}`)}
                        className="gap-2"
                      >
                        Edit <ArrowRight className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(agent.id)}
                        disabled={deleteMutation.isPending}
                        aria-label="Delete agent"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
