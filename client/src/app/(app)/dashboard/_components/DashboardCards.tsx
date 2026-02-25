'use client';

import type { ComponentType, FormEvent } from 'react';
import { useCallback, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  Bot,
  Database,
  Layers,
  LineChart,
  Loader2,
  MessageSquare,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { fetchAgentDefinitions, fetchLLMConnections } from '@/orchestration/agents';
import { resolveApiUrl } from '@/orchestration/http';
import type { AgentDefinition, LLMConnection } from '@/orchestration/agents';
import { createThread } from '@/orchestration/threads';
import type { Thread } from '@/orchestration/threads';

import { AddSourceDialog } from './AddSourceDialog';
import type { DataSource } from '../types';

const quickPrompts = [
  'Investigate revenue variance across finance and product data.',
  'Explain churn signals using CRM cohorts and usage.',
  'Summarize weekly ops health across pipelines and incidents.',
];

type FeatureHighlight = {
  title: string;
  description: string;
  href: string;
  cta: string;
  icon: ComponentType<{ className?: string }>;
};

export function DashboardCards() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { selectedOrganizationId } = useWorkspaceScope();
  const [draftPrompt, setDraftPrompt] = useState('');

  const dataSourcesQueryKey = useMemo(() => ['datasources', selectedOrganizationId] as const, [selectedOrganizationId]);
  const { data: sources, refetch } = useQuery<DataSource[]>({
    queryKey: dataSourcesQueryKey,
    enabled: Boolean(selectedOrganizationId),
    queryFn: async () => {
      if (!selectedOrganizationId) {
        return [];
      }
      const response = await fetch(resolveApiUrl(`/api/v1/datasources/${selectedOrganizationId}`), {
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        throw new Error('Failed to load data sources');
      }
      return response.json();
    },
  });

  const agentDefinitionsQuery = useQuery<AgentDefinition[]>({
    queryKey: ['agent-definitions', selectedOrganizationId],
    enabled: Boolean(selectedOrganizationId),
    queryFn: () => fetchAgentDefinitions(selectedOrganizationId),
  });

  const llmConnectionsQuery = useQuery<LLMConnection[]>({
    queryKey: ['llm-connections', selectedOrganizationId],
    enabled: Boolean(selectedOrganizationId),
    queryFn: () => fetchLLMConnections(selectedOrganizationId),
  });

  const startChatMutation = useMutation<Thread, Error>({
    mutationFn: () => {
      if (!selectedOrganizationId) {
        throw new Error('Select an organization before starting a thread.');
      }
      return createThread(selectedOrganizationId);
    },
    onError: (error) => {
      toast({ title: 'Something went wrong', description: error.message, variant: 'destructive' });
    },
  });

  const stats = useMemo(() => {
    const list = sources ?? [];

    const connected = list.filter((source) => source.status === 'connected').length;
    const pending = list.filter((source) => source.status === 'pending').length;
    const error = list.filter((source) => source.status === 'error').length;
    const total = list.length;

    return {
      total,
      connected,
      pending,
      error,
    };
  }, [sources]);

  const hasAgents = (agentDefinitionsQuery.data ?? []).length > 0;
  const hasConnections = (llmConnectionsQuery.data ?? []).length > 0;
  const canUseChat = hasAgents && hasConnections;
  const missingConnections = !hasConnections;
  const missingAgents = !hasAgents;
  const agentsBasePath = selectedOrganizationId ? `/agents/${selectedOrganizationId}` : '/agents';
  const dataSourcesBasePath = selectedOrganizationId ? `/datasources/${selectedOrganizationId}` : '/datasources';
  const semanticModelsBasePath = selectedOrganizationId ? `/semantic-model/${selectedOrganizationId}` : '/semantic-model';
  const biBasePath = selectedOrganizationId ? `/bi/${selectedOrganizationId}` : '/bi';
  const chatBasePath = selectedOrganizationId ? `/chat/${selectedOrganizationId}` : '/chat';
  const featureHighlights: FeatureHighlight[] = [
    {
      title: 'Data connections',
      description: 'Secure connectors for warehouses, SaaS tools, and APIs.',
      href: dataSourcesBasePath,
      cta: 'Manage sources',
      icon: Database,
    },
    {
      title: 'Semantic models',
      description: 'Define metrics, joins, and business language once.',
      href: semanticModelsBasePath,
      cta: 'Build a model',
      icon: Layers,
    },
    {
      title: 'Agent blueprints',
      description: 'Chain SQL, retrieval, and automations into agents.',
      href: agentsBasePath,
      cta: 'Open agents',
      icon: Bot,
    },
    {
      title: 'BI studio',
      description: 'Compose semantic queries and lightweight dashboards.',
      href: biBasePath,
      cta: 'Launch studio',
      icon: LineChart,
    },
    {
      title: 'Threaded copilot',
      description: 'Run investigations with grounded, iterative answers.',
      href: chatBasePath,
      cta: 'View threads',
      icon: MessageSquare,
    },
    {
      title: 'Workspace governance',
      description: 'Organize orgs, projects, and access controls.',
      href: '/organizations',
      cta: 'Manage workspace',
      icon: ShieldCheck,
    },
  ];

  const handleSourceCreated = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: dataSourcesQueryKey });
    await refetch();
  }, [dataSourcesQueryKey, queryClient, refetch]);

  const startChat = useCallback(
    async (prompt?: string) => {
      if (startChatMutation.isPending) {
        return;
      }
      if (!selectedOrganizationId) {
        toast({
          title: 'Select an organization',
          description: 'Choose a workspace scope before starting a thread.',
          variant: 'destructive',
        });
        return;
      }

      try {
        const thread = await startChatMutation.mutateAsync();
        toast({ title: 'Thread ready', description: 'Opening the workspace.' });
        const href =
          prompt && prompt.trim().length > 0
            ? `${chatBasePath}/${thread.id}?prompt=${encodeURIComponent(prompt.trim())}`
            : `${chatBasePath}/${thread.id}`;
        router.push(href);
      } catch (error) {
        // Error toast already handled by onError.
        console.error(error);
      }
    },
    [chatBasePath, router, selectedOrganizationId, startChatMutation, toast],
  );

  const handleDraftSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!draftPrompt.trim()) {
        return;
      }
      await startChat(draftPrompt.trim());
      setDraftPrompt('');
    },
    [draftPrompt, startChat],
  );

  return (
    <div className="relative flex min-h-full flex-col">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-24 top-0 h-72 w-72 rounded-full bg-[radial-gradient(circle,_var(--accent-soft),_transparent_70%)] blur-2xl" />
        <div className="absolute right-[-140px] top-24 h-80 w-80 rounded-full bg-[radial-gradient(circle,_rgba(56,189,248,0.18),_transparent_70%)] blur-3xl" />
      </div>

      <div className="flex-1 px-6 pb-20 pt-8 text-[color:var(--text-secondary)] transition-colors sm:px-10 lg:px-14">
        <section>
          <div className="space-y-6">
            <div className="surface-panel page-enter relative overflow-hidden rounded-3xl p-8 shadow-soft">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(16,163,127,0.15),_transparent_60%)]" />
              <div className="relative z-10 space-y-6">
                <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-[color:var(--text-muted)]">
                  <Sparkles className="h-3.5 w-3.5 text-[color:var(--accent)]" aria-hidden="true" />
                  LangBridge workspace
                </div>

                <div className="space-y-3">
                  <h2 className="text-3xl font-semibold text-[color:var(--text-primary)] sm:text-4xl">
                    Your agentic analytics command center.
                  </h2>
                  <p className="text-sm leading-relaxed text-[color:var(--text-secondary)]">
                    {stats.total === 0
                      ? 'Connect data, define semantics, and launch agents from one place.'
                      : 'Keep data, models, and agents in sync so every answer is grounded.'}
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  {canUseChat ? (
                    <Button size="lg" onClick={() => startChat()} disabled={startChatMutation.isPending}>
                      New chat
                    </Button>
                  ) : null}
                  <AddSourceDialog organizationId={selectedOrganizationId ?? undefined} onCreated={handleSourceCreated}>
                    <Button size="lg" variant="secondary" className="gap-2">
                      <Plus className="h-4 w-4" aria-hidden="true" />
                      Add source
                    </Button>
                  </AddSourceDialog>
                  <Button size="lg" variant="outline" onClick={() => router.push(biBasePath)}>
                    Open BI studio
                  </Button>
                </div>

                {canUseChat ? (
                  <>
                    <form
                      onSubmit={handleDraftSubmit}
                      className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4 shadow-sm"
                    >
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                        Ask the copilot
                      </p>
                      <Textarea
                        value={draftPrompt}
                        onChange={(event) => setDraftPrompt(event.target.value)}
                        placeholder="Ask about revenue shifts, churn drivers, or pipeline health..."
                        rows={3}
                        className="mt-3 min-h-[88px] resize-none border-none bg-transparent p-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
                        aria-label="Ask the copilot"
                      />
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                        <span className="text-xs text-[color:var(--text-muted)]">
                          Use a starter below or send your own question.
                        </span>
                        <Button
                          type="submit"
                          size="sm"
                          className="gap-2"
                          disabled={startChatMutation.isPending || draftPrompt.trim().length === 0}
                        >
                          {startChatMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                          ) : (
                            <Send className="h-4 w-4" aria-hidden="true" />
                          )}
                          Send
                        </Button>
                      </div>
                    </form>

                    <div className="flex flex-wrap gap-2 text-xs">
                      {quickPrompts.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          onClick={() => startChat(prompt)}
                          className="rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-3 py-1 text-[color:var(--text-secondary)] transition hover:border-[color:var(--border-strong)] hover:text-[color:var(--text-primary)]"
                          disabled={startChatMutation.isPending}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                      Analytics chat locked
                    </p>
                    <p className="mt-2 text-sm text-[color:var(--text-secondary)]">
                      Add an LLM connection and create an agent to unlock chat-driven analytics.
                    </p>
                    <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                      {missingConnections ? (
                        <Button
                          size="sm"
                          onClick={() => router.push(`${agentsBasePath}/llm/create`)}
                          className="gap-2"
                        >
                          Add LLM connection
                        </Button>
                      ) : (
                        <Badge variant="success">LLM connected</Badge>
                      )}
                      {missingAgents ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => router.push(`${agentsBasePath}/definitions/create`)}
                          className="gap-2"
                        >
                          Create agent
                        </Button>
                      ) : (
                        <Badge variant="success">Agent ready</Badge>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

        </section>

        <section className="mt-10">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                Platform features
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-[color:var(--text-primary)]">
                Everything you can do in LangBridge
              </h2>
            </div>
            <p className="text-sm text-[color:var(--text-secondary)]">Pick a lane and keep moving.</p>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {featureHighlights.map((feature) => (
              <FeatureCard key={feature.title} {...feature} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function FeatureCard({ title, description, href, cta, icon: Icon }: FeatureHighlight) {
  return (
    <Link
      href={href}
      className="group relative overflow-hidden rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-sm text-[color:var(--text-secondary)] shadow-soft transition hover:-translate-y-0.5 hover:border-[color:var(--border-strong)]"
    >
      <div className="pointer-events-none absolute -right-10 -top-10 h-24 w-24 rounded-full bg-[radial-gradient(circle,_var(--accent-soft),_transparent_70%)] opacity-0 transition group-hover:opacity-100" />
      <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-[color:var(--chip-bg)] text-[color:var(--accent)]">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <div className="mt-4 space-y-2">
        <h3 className="text-base font-semibold text-[color:var(--text-primary)]">{title}</h3>
        <p className="text-sm text-[color:var(--text-muted)]">{description}</p>
      </div>
      <div className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-[color:var(--accent)]">
        {cta}
        <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" aria-hidden="true" />
      </div>
    </Link>
  );
}
