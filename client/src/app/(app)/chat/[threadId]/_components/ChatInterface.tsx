'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { History, RefreshCw, Send, Sparkles } from 'lucide-react';

import { ThemeToggle } from '@/components/ThemeToggle';
import { LogoutButton } from '@/components/LogoutButton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { formatRelativeDate } from '@/lib/utils';
import {
  runThreadChat,
  type ThreadChatResponse,
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
  summary?: string | null;
  result?: ThreadTabularResult | null;
  visualization?: ThreadVisualizationSpec | null;
  errorMessage?: string;
};

type ChatInterfaceProps = {
  threadId: string;
};

export function ChatInterface({ threadId }: ChatInterfaceProps) {
  const { toast } = useToast();
  const [composer, setComposer] = useState('');
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const sendMessageMutation = useMutation<ThreadChatResponse, Error, { content: string; turnId: string }>({
    mutationFn: ({ content }) => runThreadChat(threadId, content),
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns.length, sendMessageMutation.isPending]);

  useEffect(() => {
    setTurns([]);
    setComposer('');
  }, [threadId]);

  const lastUpdated = useMemo(() => {
    const readyTurns = turns.filter((turn) => turn.status === 'ready');
    if (readyTurns.length === 0) {
      return null;
    }
    return readyTurns[readyTurns.length - 1].createdAt;
  }, [turns]);

  const isSending = sendMessageMutation.isPending;

  const submitMessage = () => {
    const trimmed = composer.trim();
    if (!trimmed || isSending) {
      return;
    }

    const turnId = `turn-${Date.now()}`;
    const createdAt = new Date().toISOString();

    setTurns((previous) => [
      ...previous,
      {
        id: turnId,
        prompt: trimmed,
        createdAt,
        status: 'pending',
      },
    ]);

    sendMessageMutation.mutate({ content: trimmed, turnId });
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

  return (
    <section className="flex h-[calc(100vh-9rem)] flex-col gap-6 py-2 text-[color:var(--text-secondary)] transition-colors">
      <header className="surface-panel flex flex-col gap-4 rounded-3xl p-6 shadow-soft sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <Badge
              variant="secondary"
              className="border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] text-[color:var(--text-secondary)]"
            >
              Thread
            </Badge>
            <span className="truncate text-sm text-[color:var(--text-muted)]" title={threadId}>
              {threadId}
            </span>
          </div>
          <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">Conversation workspace</h1>
          <p className="max-w-2xl text-sm md:text-base">
            Ask questions, run the analysis thread, and review both a visualisation and a natural-language summary for every response.
          </p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <ThemeToggle size="sm" />
          <LogoutButton />
          {lastUpdated ? (
            <p className="text-xs text-[color:var(--text-muted)]">Updated {formatRelativeDate(lastUpdated)}</p>
          ) : null}
          <Button variant="outline" size="sm" onClick={resetConversation} disabled={turns.length === 0 && !isSending}>
            <History className="mr-2 h-4 w-4" aria-hidden="true" /> Clear conversation
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-6 lg:flex-row">
        <aside className="hidden w-full max-w-xs shrink-0 flex-col gap-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 text-[color:var(--text-secondary)] shadow-soft lg:flex">
          <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Quick prompts</h2>
          <p className="text-xs text-[color:var(--text-muted)]">Jump-start the conversation with curated suggestions.</p>
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
        </aside>

        <div className="flex min-h-0 flex-1 flex-col rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] shadow-soft">
          <div
            className="flex items-center justify-between border-b border-[color:var(--panel-border)] px-6 py-4"
            aria-live="polite"
          >
            <div>
              <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Live thread</h2>
              <p className="text-xs text-[color:var(--text-muted)]">Interact with the LangBridge assistant to explore your data.</p>
            </div>
            <div className="flex items-center gap-2 text-xs text-[color:var(--text-muted)]">
              <span
                className={`inline-flex h-2 w-2 rounded-full ${isSending ? 'bg-amber-400' : 'bg-emerald-400'}`}
                aria-hidden="true"
              />
              {isSending ? 'Running analysis…' : 'Standing by'}
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col">
            <div
              className="flex-1 space-y-4 overflow-y-auto px-6 py-6"
              aria-live="polite"
              aria-label="Conversation transcript"
            >
              {turns.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
                  <Sparkles className="h-10 w-10 text-[color:var(--accent)]" aria-hidden="true" />
                  <div className="space-y-1">
                    <p className="text-base font-semibold text-[color:var(--text-primary)]">Start the conversation</p>
                    <p className="text-sm text-[color:var(--text-muted)]">
                      Ask a question or use the quick prompts to run a live planning thread with analysis, visuals, and a summary.
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    {QUICK_PROMPTS.slice(0, 2).map((prompt) => (
                      <Button key={prompt} type="button" size="sm" variant="secondary" onClick={() => applyPrompt(prompt)}>
                        <Sparkles className="mr-2 h-3.5 w-3.5 text-[color:var(--accent)]" aria-hidden="true" />
                        {prompt.replace(/\.$/, '')}
                      </Button>
                    ))}
                  </div>
                </div>
              ) : (
                <ol className="space-y-6 text-sm">
                  {turns.map((turn) => (
                    <li key={turn.id} className="space-y-3">
                      <div className="flex justify-end">
                        <div className="max-w-2xl rounded-3xl bg-[color:var(--accent)] px-5 py-3 text-sm text-white shadow-soft">
                          <p className="whitespace-pre-wrap break-words">{turn.prompt}</p>
                          <p className="mt-2 text-[10px] uppercase tracking-wider text-white/80">
                            {formatRelativeDate(turn.createdAt)}
                          </p>
                        </div>
                      </div>
                      <div className="flex justify-start">
                        <div className="flex max-w-2xl items-start gap-3">
                          <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-xs font-semibold text-[color:var(--text-primary)]">
                            AI
                          </div>
                          <div className="flex-1 space-y-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-5 py-4 shadow-soft">
                            {turn.status === 'pending' ? (
                              <div className="space-y-3">
                                <div className="flex items-center gap-2 text-xs text-[color:var(--text-muted)]">
                                  <Spinner className="h-3.5 w-3.5 text-[color:var(--accent)]" />
                                  Generating analysis&hellip;
                                </div>
                                <Skeleton className="h-4 w-48" />
                                <Skeleton className="h-4 w-64" />
                                <Skeleton className="h-24 w-full" />
                              </div>
                            ) : turn.status === 'error' ? (
                              <div className="space-y-2">
                                <p className="text-sm font-semibold text-red-500 dark:text-red-400">We couldn&apos;t complete that request.</p>
                                <p className="text-xs text-[color:var(--text-muted)]">{turn.errorMessage ?? 'An unexpected error occurred.'}</p>
                              </div>
                            ) : (
                              <div className="space-y-4 text-[color:var(--text-secondary)]">
                                <p className="text-sm leading-relaxed text-[color:var(--text-primary)]">
                                  {turn.summary ?? 'No summary was returned.'}
                                </p>
                                {turn.result ? (
                                  <ResultTable result={turn.result} />
                                ) : (
                                  <p className="text-xs text-[color:var(--text-muted)]">No tabular output was produced for this question.</p>
                                )}
                                {turn.visualization ? (
                                  <VisualizationPreview result={turn.result ?? undefined} visualization={turn.visualization ?? undefined} />
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

            <form onSubmit={handleSubmit} className="border-t border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]/90 px-6 py-4 backdrop-blur">
              <div className="rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] shadow-soft">
                <Textarea
                  value={composer}
                  onChange={(event) => setComposer(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  placeholder="Shift + Enter for a new line. Describe what you need..."
                  rows={3}
                  className="min-h-[120px] resize-none rounded-3xl border-0 bg-transparent px-5 py-4 text-base text-[color:var(--text-primary)] focus-visible:ring-0"
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
                      disabled={isSending || !composer.trim()}
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
      </div>
    </section>
  );
}
