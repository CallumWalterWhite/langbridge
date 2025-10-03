'use client';

import type { FormEvent, ReactNode } from 'react';
import { useCallback, useMemo, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, ArrowRight, LineChart, Loader2, Plus, Send, ShieldCheck, Sparkles, Workflow } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { cn, formatRelativeDate } from '@/lib/utils';
import { createChatSession } from '@/orchestration/chat';
import type { ChatSessionResponse } from '@/orchestration/chat';

import { AddSourceDialog } from './AddSourceDialog';
import { QuickAgentCreateDrawer } from './QuickAgentCreateDrawer';
import type { DataSource } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

function withApiBase(path: string) {
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE}${path}`;
}

const promptSuggestions = [
  {
    title: 'Investigate revenue variance',
    description: 'Blend finance warehouse + product telemetry to find the drivers.',
  },
  {
    title: 'Explain churn signals',
    description: 'Review CRM cohorts and usage heatmaps to surface risk accounts.',
  },
  {
    title: 'Summarise weekly ops health',
    description: 'Combine Snowflake metrics with incident notes for leadership.',
  },
  {
    title: 'Check data quality drifts',
    description: 'Scan pipelines and document retrievers for schema changes.',
  },
];

const connectorShortcuts = [
  { label: 'Snowflake', href: '/datasources/new?snowflake' },
  { label: 'Postgres', href: '/datasources/new?postgres' },
  { label: 'BigQuery', href: '/datasources/new?bigquery' },
];

const templateRecommendations = [
  {
    title: 'SQL insight loops',
    copy: 'Build reusable SQL chains with guardrailed summarisation.',
    href: '/agents?template=sql-analyst',
  },
  {
    title: 'Support intelligence',
    copy: 'Blend docs + tickets to auto-answer product questions.',
    href: '/agents?template=knowledge-concierge',
  },
  {
    title: 'Ops automation',
    copy: 'Trigger workflows when monitors spike or KPIs drift.',
    href: '/agents?template=ops-automations',
  },
];

const quickPrompts = [
  'Rank revenue signals by expected impact for next quarter.',
  'Create a retention deep-dive using product and CRM data.',
  'Generate QA checks for the finance warehouse tables.',
];

const sectionNav = [
  { id: 'overview', label: 'Overview' },
  { id: 'workspace', label: 'Workspace graph' },
  { id: 'agents', label: 'Agent blueprints' },
  { id: 'conversation', label: 'Conversation hub' },
  { id: 'activity', label: 'Ops feed' },
];

const workspaceTimeline: Array<{ title: string; caption: string; time: string; icon: typeof LineChart }> = [
  {
    title: 'Weekly metrics digest sent',
    caption: 'Agent "Northstar" shared blended ARR + adoption snapshot.',
    time: '3m ago',
    icon: LineChart,
  },
  {
    title: 'Retriever tuned',
    caption: 'Workflow "Support Radar" switched to semantic doc chunks.',
    time: '25m ago',
    icon: Workflow,
  },
  {
    title: 'New source awaiting approval',
    caption: 'Data team added Zendesk — auth pending security review.',
    time: '1h ago',
    icon: ShieldCheck,
  },
  {
    title: 'Anomaly flagged',
    caption: 'Ops agent spotted latency spike in ingestion pipeline.',
    time: '2h ago',
    icon: Activity,
  },
];

const statusVariantMap: Record<DataSource['status'], 'success' | 'destructive' | 'warning' | 'secondary'> = {
  connected: 'success',
  error: 'destructive',
  pending: 'warning',
};

const statusToneMap: Record<DataSource['status'], string> = {
  connected: 'border border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-200',
  pending: 'border border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-200',
  error: 'border border-rose-500/25 bg-rose-500/15 text-rose-600 dark:text-rose-100',
};

export function DashboardCards() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [draftPrompt, setDraftPrompt] = useState('');

  const { data: sources, isLoading, isError, refetch } = useQuery<DataSource[]>({
    queryKey: ['datasources'],
    queryFn: async () => {
      const response = await fetch(withApiBase('/api/v1/datasources'), {
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        throw new Error('Failed to load data sources');
      }
      return response.json();
    },
  });

  const startChatMutation = useMutation<ChatSessionResponse, Error>({
    mutationFn: () => createChatSession(),
    onError: (error) => {
      toast({ title: 'Something went wrong', description: error.message, variant: 'destructive' });
    },
  });

  const { recentSources, stats } = useMemo(() => {
    const list = sources ?? [];
    const recent = list.slice(0, 4);

    const connected = list.filter((source) => source.status === 'connected').length;
    const pending = list.filter((source) => source.status === 'pending').length;
    const error = list.filter((source) => source.status === 'error').length;
    const total = list.length;

    return {
      recentSources: recent,
      stats: {
        total,
        connected,
        pending,
        error,
        readyPercentage: total === 0 ? 0 : Math.round((connected / total) * 100),
      },
    };
  }, [sources]);

  const handleSourceCreated = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['datasources'] });
    await refetch();
  }, [queryClient, refetch]);

  const startChat = useCallback(
    async (prompt?: string) => {
      if (startChatMutation.isPending) {
        return;
      }

      try {
        const { sessionId } = await startChatMutation.mutateAsync();
        toast({ title: 'Chat session ready', description: 'Opening the workspace.' });
        const href = prompt && prompt.trim().length > 0 ? `/chat/${sessionId}?prompt=${encodeURIComponent(prompt.trim())}` : `/chat/${sessionId}`;
        router.push(href);
      } catch (error) {
        // Error toast already handled by onError.
        console.error(error);
      }
    },
    [router, startChatMutation, toast],
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

  const metaLabel = isLoading
    ? 'Syncing workspace...'
    : stats.total === 0
      ? 'No connectors yet — add one below to get started.'
      : `${stats.total} sources • ${stats.connected} ready • ${stats.pending} pending`;

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex-1 px-6 pb-32 pt-8 text-[color:var(--text-secondary)] transition-colors sm:px-10 lg:px-14">
        <div className="flex flex-col gap-6" id="overview">
          <nav className="flex w-full overflow-x-auto rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-1 text-xs font-medium text-[color:var(--text-secondary)] shadow-soft">
            {sectionNav.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="flex-1 rounded-full px-4 py-2 text-center transition hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]"
              >
                {item.label}
              </a>
            ))}
          </nav>

          <AssistantMessage heading="Good to see you. What should we explore?" meta={metaLabel}>
            {stats.total === 0 ? (
              <p className="text-sm text-[color:var(--text-secondary)]">
                Hook up Snowflake, BigQuery, internal APIs, or ticketing systems. I&apos;ll unify them into a single
                retrieval layer so you can ask one question and reason across all of them.
              </p>
            ) : (
              <p className="text-sm text-[color:var(--text-secondary)]">
                I&apos;m monitoring your connected sources and retrievers. Ask a question, fire off a workflow, or drill
                deeper with the quick starters below.
              </p>
            )}
          </AssistantMessage>
        </div>

        <div className="mt-8 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {promptSuggestions.map((suggestion) => (
            <button
              key={suggestion.title}
              type="button"
              onClick={() => startChat(suggestion.title)}
              className="group rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 text-left transition hover:-translate-y-0.5 hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-alt)]"
              disabled={startChatMutation.isPending}
            >
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">{suggestion.title}</h2>
                <ArrowRight className="h-4 w-4 text-[color:var(--text-muted)] transition group-hover:translate-x-1 group-hover:text-[color:var(--text-primary)]" aria-hidden="true" />
              </div>
              <p className="mt-2 text-xs text-[color:var(--text-muted)]">{suggestion.description}</p>
            </button>
          ))}
        </div>

        <div className="mt-12 grid gap-6 xl:grid-cols-12">
          <AssistantPanel
            id="workspace"
            title="Workspace graph"
            description="Connect, monitor, and score the sources feeding your agentic BI copilot."
            actions={
              <AddSourceDialog onCreated={handleSourceCreated}>
                <Button
                  type="button"
                  size="sm"
                  className="gap-2"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Add source
                </Button>
              </AddSourceDialog>
            }
            className="xl:col-span-7"
          >
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Recent sources</p>
              <div className="mt-4 space-y-3" aria-live="polite">
                {isLoading ? (
                  <>
                    {Array.from({ length: 3 }).map((_, index) => (
                      <div key={index} className="space-y-2 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4">
                        <Skeleton className="h-4 w-1/3 bg-[color:var(--surface-muted)]" />
                        <Skeleton className="h-3 w-1/2 bg-[color:var(--surface-muted)]" />
                      </div>
                    ))}
                  </>
                ) : isError ? (
                  <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-5 py-6 text-sm">
                    Unable to load data sources.
                    <button
                      type="button"
                      className="ml-2 text-[color:var(--text-primary)] underline-offset-4 hover:underline"
                      onClick={() => refetch()}
                    >
                      Retry
                    </button>
                  </div>
                ) : recentSources.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-5 py-6 text-sm">
                    No sources yet. Plug in a warehouse or SaaS system to unlock cross-source answering.
                  </div>
                ) : (
                  <ul className="space-y-3" aria-label="Recent data sources">
                    {recentSources.map((source) => (
                      <li
                        key={source.id}
                        className="flex items-center justify-between gap-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-3"
                      >
                        <div className="flex items-center gap-3">
                          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[color:var(--chip-bg)] text-xs font-semibold uppercase text-[color:var(--text-primary)]">
                            {source.type.slice(0, 2)}
                          </span>
                          <div>
                            <p className="text-sm font-semibold text-[color:var(--text-primary)]">{source.name}</p>
                            <p className="text-xs text-[color:var(--text-muted)]">
                              {source.type.toUpperCase()} · {formatRelativeDate(source.createdAt)}
                            </p>
                          </div>
                        </div>
                        <Badge
                          variant={statusVariantMap[source.status]}
                          className={statusToneMap[source.status]}
                        >
                          {statusLabel(source.status)}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div className="grid gap-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 sm:grid-cols-3">
              <div>
                <p className="text-xs text-[color:var(--text-muted)]">Ready for agents</p>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[color:var(--surface-muted)]">
                  <div
                    className="h-full rounded-full bg-emerald-500"
                    style={{ width: `${stats.readyPercentage}%` }}
                  />
                </div>
                <p className="mt-2 text-sm font-semibold text-[color:var(--text-primary)]">{stats.readyPercentage}%</p>
              </div>
              <div>
                <p className="text-xs text-[color:var(--text-muted)]">Connected</p>
                <p className="mt-2 text-2xl font-semibold text-[color:var(--text-primary)]">{stats.connected}</p>
              </div>
              <div>
                <p className="text-xs text-[color:var(--text-muted)]">Pending / issues</p>
                <p className="mt-2 text-2xl font-semibold text-[color:var(--text-primary)]">
                  {stats.pending + stats.error}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {connectorShortcuts.map((shortcut) => (
                <Link
                  key={shortcut.label}
                  href={shortcut.href}
                  className="inline-flex items-center gap-2 rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-2 text-xs font-medium text-[color:var(--text-secondary)] transition hover:border-[color:var(--border-strong)] hover:text-[color:var(--text-primary)]"
                >
                  {shortcut.label}
                  <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                </Link>
              ))}
            </div>
          </AssistantPanel>

          <AssistantPanel
            id="agents"
            title="Agent blueprints"
            description="Spin up orchestrations that chain retrieval, SQL, and automations for every business unit."
            actions={
              <Button
                size="sm"
                variant="secondary"
                onClick={() => router.push('/agents')}
                className="gap-2"
              >
                Manage agents
              </Button>
            }
            className="xl:col-span-5"
          >
            <QuickAgentCreateDrawer
              sources={sources ?? []}
              onCreated={(agentId) => router.push(`/agents/${agentId}`)}
            />

            <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--border-strong)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium text-[color:var(--text-secondary)]">
              <Sparkles className="h-3.5 w-3.5 text-[color:var(--accent)]" aria-hidden="true" />
              Recommended playbooks
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {templateRecommendations.map((template) => (
                <button
                  key={template.title}
                  type="button"
                  onClick={() => router.push(template.href)}
                  className="group flex h-full flex-col justify-between gap-2 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-4 text-left text-sm text-[color:var(--text-secondary)] transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]"
                >
                  <span className="text-sm font-semibold text-[color:var(--text-primary)]">{template.title}</span>
                  <span className="text-xs leading-relaxed text-[color:var(--text-muted)]">{template.copy}</span>
                  <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-[color:var(--accent)]">
                    Open template
                    <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" aria-hidden="true" />
                  </span>
                </button>
              ))}
            </div>
          </AssistantPanel>

          <AssistantPanel
            id="conversation"
            title="Conversation hub"
            description="Jump into a new investigation or revisit a thread. Responses stay grounded in your authorised sources."
            actions={
              <Button
                size="sm"
                variant="secondary"
                onClick={() => router.push('/chat')}
                className="gap-2"
              >
                History
              </Button>
            }
            className="xl:col-span-7"
          >
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                size="lg"
                className="w-full rounded-2xl shadow-soft"
                onClick={() => startChat()}
                disabled={startChatMutation.isPending}
              >
                Start a new chat
              </Button>
              <Button
                variant="ghost"
                className="w-full rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-secondary)] transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]"
                onClick={() => router.push('/chat')}
              >
                View recent chats
              </Button>
            </div>

            <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Quick prompts</p>
              <ul className="mt-3 space-y-3 text-sm text-[color:var(--text-secondary)]">
                {quickPrompts.map((prompt) => (
                  <li key={prompt}>
                    <button
                      type="button"
                      onClick={() => startChat(prompt)}
                      className="group flex w-full items-start gap-2 rounded-xl border border-transparent px-3 py-2 text-left transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--chip-bg)]"
                      disabled={startChatMutation.isPending}
                    >
                      <span className="mt-[2px] text-[color:var(--accent)]">&gt;</span>
                      <span className="group-hover:text-[color:var(--text-primary)]">{prompt}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </AssistantPanel>

          <AssistantPanel
            id="activity"
            title="Ops & activity feed"
            description="Keep tabs on what the copilot shipped, queued, or flagged across the workspace."
            className="xl:col-span-5"
          >
            <ol className="space-y-4">
              {workspaceTimeline.map(({ title, caption, time, icon: Icon }) => (
                <li key={title} className="flex items-start gap-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-3 transition hover:border-[color:var(--border-strong)]">
                  <span className="mt-1 flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-[color:var(--accent)]">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-[color:var(--text-primary)]">{title}</p>
                    <p className="text-xs text-[color:var(--text-muted)]">{caption}</p>
                    <p className="text-xs text-[color:var(--text-muted)]">{time}</p>
                  </div>
                </li>
              ))}
            </ol>
          </AssistantPanel>
        </div>
      </div>

      <form
        onSubmit={handleDraftSubmit}
        className="pointer-events-auto sticky bottom-6 flex justify-center px-4 sm:px-6"
      >
        <div className="w-full max-w-3xl rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-2 shadow-soft">
          <textarea
            value={draftPrompt}
            onChange={(event) => setDraftPrompt(event.target.value)}
            placeholder="Send a message..."
            rows={1}
            className="min-h-[24px] w-full resize-none bg-transparent px-3 py-2 text-sm text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] focus:outline-none"
            aria-label="Message the copilot"
          />
          <div className="flex items-center justify-end gap-2 px-3 pb-1">
            <Button
              type="submit"
              size="sm"
              className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold"
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
        </div>
      </form>
    </div>
  );
}

function AssistantMessage({ heading, meta, children }: { heading: string; meta?: string; children: ReactNode }) {
  return (
    <div className="surface-panel rounded-3xl p-6 shadow-soft">
      <div className="flex items-start gap-4">
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[color:var(--accent-soft)] text-[color:var(--accent)]">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="space-y-2">
          <div>
            <p className="text-sm font-semibold text-[color:var(--text-primary)]">{heading}</p>
            {meta ? <p className="text-xs text-[color:var(--text-muted)]">{meta}</p> : null}
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}

function AssistantPanel({
  title,
  description,
  actions,
  children,
  id,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
  className?: string;
}) {
  return (
    <section
      id={id}
      className={cn('surface-panel rounded-3xl p-6 text-[color:var(--text-secondary)] transition-colors', className)}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">{title}</p>
          {description ? <p className="mt-2 text-sm">{description}</p> : null}
        </div>
        {actions ? <div className="flex items-center gap-2 text-[color:var(--text-secondary)]">{actions}</div> : null}
      </div>
      <div className="mt-5 space-y-5 text-sm text-[color:var(--text-secondary)]">{children}</div>
    </section>
  );
}

function statusLabel(status: DataSource['status']) {
  switch (status) {
    case 'connected':
      return 'Connected';
    case 'pending':
      return 'Pending';
    case 'error':
      return 'Needs attention';
    default:
      return status;
  }
}
