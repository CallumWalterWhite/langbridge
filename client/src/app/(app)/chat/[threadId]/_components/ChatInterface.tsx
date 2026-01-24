'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { History, Pencil, RefreshCw, Send, Sparkles } from 'lucide-react';

import { ThemeToggle } from '@/components/ThemeToggle';
import { LogoutButton } from '@/components/LogoutButton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { formatRelativeDate } from '@/lib/utils';
import { fetchAgentDefinitions, type AgentDefinition } from '@/orchestration/agents';
import {
  fetchThread,
  listThreadMessages,
  runThreadChat,
  updateThread,
  type Thread,
  type ThreadChatResponse,
  type ThreadMessage,
  type ThreadTabularResult,
  type ThreadVisualizationSpec,
} from '@/orchestration/threads';

import { ResultTable } from './ResultTable';
import { VisualizationPreview } from './VisualizationPreview';

const QUICK_PROMPTS = [
  'Summarize the latest metrics across all data sources.',
  'List key anomalies that surfaced this week.',
  "Draft a brief for leadership using today's updates.",
  'Generate follow-up questions I should ask next.',
];

type ConversationTurn = {
  id: string;
  prompt: string;
  createdAt: string;
  status: 'pending' | 'ready' | 'error';
  agentId?: string;
  agentLabel?: string;
  summary?: string | null;
  result?: ThreadTabularResult | null;
  visualization?: ThreadVisualizationSpec | null;
  errorMessage?: string;
};

type ChatInterfaceProps = {
  threadId: string;
  organizationId: string;
};

const readTextField = (value: unknown): string | undefined => {
  return typeof value === 'string' ? value : undefined;
};

const extractAgentMeta = (message: ThreadMessage | undefined) => {
  if (!message) {
    return { agentId: undefined, agentLabel: undefined };
  }
  const snapshot = message.modelSnapshot ?? {};
  const agentId = readTextField(snapshot.agent_id ?? snapshot.agentId);
  const agentLabel = readTextField(snapshot.agent_name ?? snapshot.agentName);
  return { agentId, agentLabel };
};

const buildTurnsFromMessages = (messages: ThreadMessage[]): ConversationTurn[] => {
  if (messages.length === 0) {
    return [];
  }
  const assistantByParent = new Map<string, ThreadMessage>();
  messages
    .filter((message) => message.role === 'assistant')
    .forEach((message) => {
      if (message.parentMessageId) {
        assistantByParent.set(message.parentMessageId, message);
      }
    });

  return messages
    .filter((message) => message.role === 'user')
    .map((message, index) => {
      const assistant = assistantByParent.get(message.id);
      const content = message.content ?? {};
      const assistantContent = assistant?.content ?? {};
      const { agentId, agentLabel } = extractAgentMeta(assistant ?? message);
      const errorMessage = readTextField((assistant?.error as Record<string, unknown> | undefined)?.message);

      return {
        id: message.id ?? `history-${index}`,
        prompt: readTextField(content.text) ?? '',
        createdAt: message.createdAt ?? new Date().toISOString(),
        status: assistant ? (assistant.error ? 'error' : 'ready') : 'pending',
        agentId,
        agentLabel,
        summary: readTextField(assistantContent.summary) ?? null,
        result: (assistantContent.result as ThreadTabularResult | null | undefined) ?? null,
        visualization: (assistantContent.visualization as ThreadVisualizationSpec | null | undefined) ?? null,
        errorMessage: errorMessage || undefined,
      };
    });
};

export function ChatInterface({ threadId, organizationId }: ChatInterfaceProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [composer, setComposer] = useState('');
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [threadTitle, setThreadTitle] = useState<string | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [renameError, setRenameError] = useState<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const agentDefinitionsQuery = useQuery<AgentDefinition[]>({
    queryKey: ['agent-definitions', organizationId],
    enabled: Boolean(organizationId),
    queryFn: () => fetchAgentDefinitions(organizationId),
  });

  const historyQuery = useQuery<ThreadMessage[]>({
    queryKey: ['thread-messages', organizationId, threadId],
    queryFn: () => listThreadMessages(organizationId, threadId),
  });

  const threadQuery = useQuery<Thread>({
    queryKey: ['thread', organizationId, threadId],
    queryFn: () => fetchThread(organizationId, threadId),
  });

  const agentOptions = useMemo(() => {
    return (agentDefinitionsQuery.data ?? []).slice().sort((a, b) => a.name.localeCompare(b.name));
  }, [agentDefinitionsQuery.data]);

  const agentLabelById = useMemo(() => {
    return new Map(agentOptions.map((agent) => [agent.id, agent.name]));
  }, [agentOptions]);

  const selectedAgent = useMemo(() => {
    return agentOptions.find((agent) => agent.id === selectedAgentId) ?? null;
  }, [agentOptions, selectedAgentId]);

  const sendMessageMutation = useMutation<
    ThreadChatResponse,
    Error,
    { content: string; turnId: string; agentId: string }
  >({
    mutationFn: ({ content, agentId }) => runThreadChat(organizationId, threadId, content, agentId),
    onSuccess: (data, variables) => {
      setTurns((previous) =>
        previous.map((turn) =>
          turn.id === variables.turnId
            ? {
                ...turn,
                status: 'ready',
                summary: data.summary ?? 'No summary was provided.',
                result: data.result ?? null,
                visualization: data.visualization ?? null,
                errorMessage: undefined,
              }
            : turn,
        ),
      );
    },
    onError: (error, variables) => {
      setTurns((previous) =>
        previous.map((turn) =>
          turn.id === variables.turnId
            ? { ...turn, status: 'error', errorMessage: error.message || 'Unable to complete this request.' }
            : turn,
        ),
      );
      toast({
        title: 'Request failed',
        description: error.message || 'The assistant was unable to respond.',
        variant: 'destructive',
      });
    },
  });

  const renameThreadMutation = useMutation<Thread, Error, { title: string }>({
    mutationFn: ({ title }) => updateThread(organizationId, threadId, { title }),
    onSuccess: (updated) => {
      setThreadTitle(updated.title ?? null);
      setRenameOpen(false);
      setRenameValue('');
      setRenameError(null);
      queryClient.invalidateQueries({ queryKey: ['thread', organizationId, threadId] });
      queryClient.invalidateQueries({ queryKey: ['chat-threads', organizationId] });
      toast({ title: 'Thread renamed', description: 'Your thread title has been updated.' });
    },
    onError: (error) => {
      const message = error.message || 'Unable to rename this thread.';
      setRenameError(message);
      toast({ title: 'Rename failed', description: message, variant: 'destructive' });
    },
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns.length, sendMessageMutation.isPending]);

  useEffect(() => {
    setTurns([]);
    setComposer('');
    setHistoryLoaded(false);
    const storageKey = `thread-agent:${threadId}`;
    const storedAgentId = window.localStorage.getItem(storageKey);
    setSelectedAgentId(storedAgentId ?? '');
    setThreadTitle(null);
  }, [threadId]);

  useEffect(() => {
    const storageKey = `thread-agent:${threadId}`;
    if (!selectedAgentId) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, selectedAgentId);
  }, [selectedAgentId, threadId]);

  useEffect(() => {
    if (!agentDefinitionsQuery.isSuccess) {
      return;
    }
    if (agentOptions.length === 0) {
      setSelectedAgentId('');
      return;
    }
    if (selectedAgentId && !selectedAgent) {
      setSelectedAgentId('');
    }
  }, [agentDefinitionsQuery.isSuccess, agentOptions.length, selectedAgent, selectedAgentId]);

  const lastUpdated = useMemo(() => {
    const readyTurns = turns.filter((turn) => turn.status === 'ready');
    if (readyTurns.length === 0) {
      return null;
    }
    return readyTurns[readyTurns.length - 1].createdAt;
  }, [turns]);

  const isSending = sendMessageMutation.isPending;
  const hasAgents = agentOptions.length > 0;
  const isLoadingAgents = agentDefinitionsQuery.isLoading;
  const agentStatusLabel =
    selectedAgent?.name ?? (isLoadingAgents ? 'Loading agents...' : hasAgents ? 'Select an agent' : 'No agents available');
  const agentsBasePath = organizationId ? `/agents/${organizationId}` : '/agents';

  const submitMessage = () => {
    const trimmed = composer.trim();
    if (!trimmed || isSending) {
      return;
    }
    if (!selectedAgentId) {
      toast({
        title: hasAgents ? 'Select an agent' : 'No agents available',
        description: hasAgents
          ? 'Choose an agent before sending a prompt.'
          : 'Create an agent to start this thread.',
        variant: 'destructive',
      });
      return;
    }

    const turnId = `turn-${Date.now()}`;
    const createdAt = new Date().toISOString();
    const agentLabel = selectedAgent?.name ?? 'Unknown agent';
    const agentId = selectedAgentId;

    setTurns((previous) => [
      ...previous,
      {
        id: turnId,
        prompt: trimmed,
        createdAt,
        status: 'pending',
        agentId,
        agentLabel,
      },
    ]);

    sendMessageMutation.mutate({ content: trimmed, turnId, agentId });
    setComposer('');
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitMessage();
  };

  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitMessage();
    }
  };

  const applyPrompt = (prompt: string) => {
    setComposer((value) => (value ? `${value}\n${prompt}` : prompt));
  };

  const handleRegenerate = () => {
    if (turns.length === 0) {
      toast({
        title: 'Nothing to regenerate',
        description: 'Send a prompt before trying to regenerate the response.',
        variant: 'destructive',
      });
      return;
    }

    const lastTurn = [...turns].reverse().find((turn) => turn.status !== 'pending');
    if (!lastTurn) {
      toast({
        title: 'Still processing',
        description: 'Wait for the current response to finish before regenerating.',
        variant: 'destructive',
      });
      return;
    }
    setComposer(lastTurn.prompt);
  };

  const resetConversation = () => {
    setTurns([]);
  };

  useEffect(() => {
    if (historyLoaded || !historyQuery.isSuccess) {
      return;
    }
    const historyTurns = buildTurnsFromMessages(historyQuery.data ?? []);
    const historyIds = new Set(historyTurns.map((turn) => turn.id));
    const mergedTurns =
      turns.length > 0 ? [...historyTurns, ...turns.filter((turn) => !historyIds.has(turn.id))] : historyTurns;
    setTurns(mergedTurns);
    setHistoryLoaded(true);
    if (!selectedAgentId) {
      const lastAgentId = [...historyTurns].reverse().find((turn) => turn.agentId)?.agentId;
      if (lastAgentId) {
        setSelectedAgentId(lastAgentId);
      }
    }
  }, [historyLoaded, historyQuery.data, historyQuery.isSuccess, selectedAgentId, turns]);

  useEffect(() => {
    if (!threadQuery.data) {
      return;
    }
    setThreadTitle(threadQuery.data.title ?? null);
  }, [threadQuery.data]);

  useEffect(() => {
    if (!renameOpen) {
      setRenameError(null);
      return;
    }
    setRenameValue(threadTitle ?? '');
  }, [renameOpen, threadTitle]);

  const handleRenameSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = renameValue.trim();
    if (!trimmed) {
      setRenameError('Title is required.');
      return;
    }
    renameThreadMutation.mutate({ title: trimmed });
  };

  const threadLabel = threadTitle?.trim() || `Thread ${threadId.slice(0, 8)}`;

  return (
    <section className="flex h-[calc(100vh-8rem)] flex-col gap-4 py-2 text-[color:var(--text-secondary)] transition-colors">
      <header className="surface-panel flex flex-wrap items-center justify-between gap-4 rounded-2xl px-4 py-3 shadow-soft">
        <div className="flex flex-wrap items-center gap-3">
          <Badge
            variant="secondary"
            className="border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] text-[color:var(--text-secondary)]"
          >
            Thread
          </Badge>
          <span className="text-xs font-semibold text-[color:var(--text-primary)]">{threadLabel}</span>
          <span className="truncate text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-muted)]" title={threadId}>
            {threadId}
          </span>
          <span className="text-xs text-[color:var(--text-muted)]">Agent: {agentStatusLabel}</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Select
            value={selectedAgentId}
            onChange={(event) => setSelectedAgentId(event.target.value)}
            disabled={isLoadingAgents || agentOptions.length === 0}
            aria-label="Select active agent"
            className="h-9 min-w-[200px]"
          >
            {isLoadingAgents ? (
              <option value="" disabled>
                Loading agents...
              </option>
            ) : agentOptions.length === 0 ? (
              <option value="" disabled>
                No agents available
              </option>
            ) : (
              <option value="" disabled>
                Select an agent
              </option>
            )}
            {agentOptions.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </Select>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => router.push(`${agentsBasePath}/definitions`)}
            disabled={agentDefinitionsQuery.isLoading}
          >
            Manage agents
          </Button>
          <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
            <DialogTrigger asChild>
              <Button type="button" variant="ghost" size="sm" className="gap-2">
                <Pencil className="h-4 w-4" aria-hidden="true" />
                Rename
              </Button>
            </DialogTrigger>
            <DialogContent>
              <form onSubmit={handleRenameSubmit} className="space-y-4">
                <DialogHeader>
                  <DialogTitle>Rename thread</DialogTitle>
                </DialogHeader>
                <div className="space-y-2">
                  <Input
                    value={renameValue}
                    onChange={(event) => setRenameValue(event.target.value)}
                    placeholder="e.g. Q4 pipeline review"
                    autoFocus
                  />
                  {renameError ? <p className="text-xs text-rose-500">{renameError}</p> : null}
                </div>
                <DialogFooter className="gap-2 sm:gap-3">
                  <DialogClose asChild>
                    <Button type="button" variant="ghost">
                      Cancel
                    </Button>
                  </DialogClose>
                  <Button type="submit" disabled={renameThreadMutation.isPending}>
                    {renameThreadMutation.isPending ? 'Saving...' : 'Save'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={resetConversation}
            disabled={turns.length === 0 && !isSending}
          >
            <History className="h-4 w-4" aria-hidden="true" />
            Clear
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-6 lg:flex-row">
        <div className="flex min-h-0 flex-1 flex-col rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] shadow-soft">
          <div
            className="flex flex-col gap-3 border-b border-[color:var(--panel-border)] px-6 py-3 md:flex-row md:items-center md:justify-between"
            aria-live="polite"
          >
            <div>
              <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Thread timeline</h2>
              <p className="text-xs text-[color:var(--text-muted)]">
                Messages, summaries, and artifacts generated for this thread.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-[color:var(--text-muted)]">
              <div className="flex items-center gap-2">
                <span
                  className={`inline-flex h-2 w-2 rounded-full ${isSending ? 'bg-amber-400' : 'bg-emerald-400'}`}
                  aria-hidden="true"
                />
                {isSending ? 'Generating response...' : 'Standing by'}
              </div>
              <span>{lastUpdated ? `Updated ${formatRelativeDate(lastUpdated)}` : 'Awaiting first prompt'}</span>
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6" aria-live="polite" aria-label="Thread transcript">
              {turns.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
                  <Sparkles className="h-10 w-10 text-[color:var(--accent)]" aria-hidden="true" />
                  <div className="space-y-1">
                    <p className="text-base font-semibold text-[color:var(--text-primary)]">
                      {isLoadingAgents ? 'Loading agents' : hasAgents ? 'Start the thread' : 'Create your first agent'}
                    </p>
                    <p className="text-sm text-[color:var(--text-muted)]">
                      {isLoadingAgents
                        ? 'Fetching your agent roster for this workspace.'
                        : hasAgents
                          ? 'Pick an agent and send a prompt to generate responses, visuals, and summaries.'
                          : 'Agents you create will appear here for new conversations.'}
                    </p>
                  </div>
                  {hasAgents ? (
                    <div className="flex flex-wrap justify-center gap-2">
                      {QUICK_PROMPTS.slice(0, 2).map((prompt) => (
                        <Button key={prompt} type="button" size="sm" variant="secondary" onClick={() => applyPrompt(prompt)}>
                          <Sparkles className="mr-2 h-3.5 w-3.5 text-[color:var(--accent)]" aria-hidden="true" />
                          {prompt.replace(/\.$/, '')}
                        </Button>
                      ))}
                    </div>
                  ) : isLoadingAgents ? null : (
                    <Button type="button" size="sm" onClick={() => router.push(`${agentsBasePath}/definitions`)}>
                      Create an agent
                    </Button>
                  )}
                </div>
              ) : (
                <ol className="space-y-6 text-sm">
                  {turns.map((turn) => (
                    <li key={turn.id} className="space-y-3">
                      <div className="flex justify-end">
                        <div className="max-w-4xl rounded-3xl bg-[color:var(--accent)] px-5 py-3 text-sm text-white shadow-soft">
                          <p className="whitespace-pre-wrap break-words">{turn.prompt}</p>
                          <p className="mt-2 text-[10px] uppercase tracking-wider text-white/80">
                            {formatRelativeDate(turn.createdAt)}
                          </p>
                        </div>
                      </div>
                      <div className="flex justify-start">
                        <div className="flex max-w-4xl items-start gap-3">
                          <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-xs font-semibold text-[color:var(--text-primary)]">
                            AI
                          </div>
                          <div className="flex-1 space-y-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-5 py-4 shadow-soft">
                            <div className="flex items-center justify-between text-xs text-[color:var(--text-muted)]">
                              <span>
                                Agent:{' '}
                                {turn.agentLabel ??
                                  (turn.agentId ? agentLabelById.get(turn.agentId) : undefined) ??
                                  'Unknown agent'}
                              </span>
                              <span className="uppercase tracking-[0.2em]">
                                {turn.status === 'pending'
                                  ? 'Processing'
                                  : turn.status === 'error'
                                    ? 'Error'
                                    : 'Complete'}
                              </span>
                            </div>
                            {turn.status === 'pending' ? (
                              <div className="space-y-3">
                                <div className="flex items-center gap-2 text-xs text-[color:var(--text-muted)]">
                                  <Spinner className="h-3.5 w-3.5 text-[color:var(--accent)]" />
                                  Generating response&hellip;
                                </div>
                                <Skeleton className="h-4 w-48" />
                                <Skeleton className="h-4 w-64" />
                                <Skeleton className="h-24 w-full" />
                              </div>
                            ) : turn.status === 'error' ? (
                              <div className="space-y-2">
                                <p className="text-sm font-semibold text-red-500 dark:text-red-400">
                                  We couldn&apos;t complete that request.
                                </p>
                                <p className="text-xs text-[color:var(--text-muted)]">
                                  {turn.errorMessage ?? 'An unexpected error occurred.'}
                                </p>
                              </div>
                            ) : (
                              <div className="space-y-4 text-[color:var(--text-secondary)]">
                                <p className="text-sm leading-relaxed text-[color:var(--text-primary)]">
                                  {turn.summary ?? 'No summary was returned.'}
                                </p>
                                {turn.result ? (
                                  <ResultTable result={turn.result} />
                                ) : (
                                  <p className="text-xs text-[color:var(--text-muted)]">
                                    No tabular output was produced for this question.
                                  </p>
                                )}
                                {turn.visualization ? (
                                  <VisualizationPreview
                                    result={turn.result ?? undefined}
                                    visualization={turn.visualization ?? undefined}
                                  />
                                ) : null}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSubmit} className="border-t border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]/95 px-6 py-4 backdrop-blur">
              <div className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] shadow-soft">
                <Textarea
                  value={composer}
                  onChange={(event) => setComposer(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  placeholder="Shift + Enter for a new line. Describe what you need..."
                  rows={4}
                  className="min-h-[160px] resize-none rounded-3xl border-0 bg-transparent px-5 py-4 text-base text-[color:var(--text-primary)] focus-visible:ring-0"
                  aria-label="Message LangBridge assistant"
                />
                <div className="flex flex-col gap-3 border-t border-[color:var(--panel-border)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap gap-2">
                    {QUICK_PROMPTS.slice(0, 2).map((prompt) => (
                      <Button key={prompt} type="button" size="sm" variant="secondary" onClick={() => applyPrompt(prompt)}>
                        <Sparkles className="mr-2 h-3.5 w-3.5 text-[color:var(--accent)]" aria-hidden="true" />
                        {prompt.replace(/\.$/, '')}
                      </Button>
                    ))}
                  </div>
                  <div className="flex items-center gap-3">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                      onClick={handleRegenerate}
                      disabled={turns.length === 0}
                    >
                      <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
                      Regenerate
                    </Button>
                    <Button
                      type="submit"
                      size="sm"
                      className="gap-2"
                      disabled={isSending || !composer.trim() || !selectedAgentId}
                      isLoading={isSending}
                      loadingText="Sending..."
                    >
                      <Send className="h-4 w-4" aria-hidden="true" />
                      Send
                    </Button>
                  </div>
                </div>
              </div>
            </form>
          </div>
        </div>
        <aside className="hidden w-full max-w-sm shrink-0 flex-col gap-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 text-[color:var(--text-secondary)] shadow-soft lg:flex">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Recommendations</p>
            <h2 className="text-base font-semibold text-[color:var(--text-primary)]">Prompt starters</h2>
            <p className="text-xs text-[color:var(--text-muted)]">Use a starter to shape the next response.</p>
          </div>
          <div className="space-y-2">
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => applyPrompt(prompt)}
                className="w-full rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-3 text-left text-xs text-[color:var(--text-secondary)] transition hover:-translate-y-0.5 hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-bg)]"
              >
                {prompt}
              </button>
            ))}
          </div>
          <div className="mt-auto rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-3 text-xs text-[color:var(--text-muted)]">
            {agentDefinitionsQuery.isError
              ? 'Agent profiles are unavailable right now.'
              : selectedAgent?.description ||
                (hasAgents ? 'Select an agent to view its description.' : 'Create an agent to see its profile here.')}
          </div>
        </aside>
      </div>
    </section>
  );
}
