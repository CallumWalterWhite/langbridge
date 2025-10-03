'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { History, RefreshCw, Send, Sparkles } from 'lucide-react';

import { ThemeToggle } from '@/components/ThemeToggle';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { formatRelativeDate } from '@/lib/utils';
import { createChatMessage, listChatMessages } from '@/orchestration/chat';
import type { ChatMessage, ChatMessagePair } from '@/orchestration/chat';

const QUICK_PROMPTS = [
  'Summarize the latest metrics across all data sources.',
  'List key anomalies that surfaced this week.',
  'Draft a brief for leadership using today\'s updates.',
  'Generate follow-up questions I should ask next.',
];

type ChatInterfaceProps = {
  sessionId: string;
};

export function ChatInterface({ sessionId }: ChatInterfaceProps) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [composer, setComposer] = useState('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const queryKey = ['chat-messages', sessionId] as const;

  const chatQuery = useQuery<ChatMessage[]>({
    queryKey,
    queryFn: () => listChatMessages(sessionId),
    refetchInterval: 8000,
  });

  const messages = useMemo(() => chatQuery.data ?? [], [chatQuery.data]);

  const sendMessageMutation = useMutation<ChatMessagePair, Error, { content: string }, { snapshot: ChatMessage[]; optimisticId: string }>(
    {
      mutationFn: ({ content }) => createChatMessage(sessionId, content),
      onMutate: async ({ content }) => {
        await queryClient.cancelQueries({ queryKey });
        const previousMessages = queryClient.getQueryData<ChatMessage[]>(queryKey) ?? [];
        const optimisticMessage: ChatMessage = {
          id: `temp-${Date.now()}`,
          sessionId,
          role: 'user',
          content,
          createdAt: new Date().toISOString(),
        };

        queryClient.setQueryData<ChatMessage[]>(queryKey, [...previousMessages, optimisticMessage]);

        return { snapshot: previousMessages, optimisticId: optimisticMessage.id };
      },
      onError: (error, _variables, context) => {
        queryClient.setQueryData(queryKey, context?.snapshot ?? []);
        toast({ title: 'Message failed', description: error.message, variant: 'destructive' });
      },
      onSuccess: (pair, _variables, context) => {
        queryClient.setQueryData<ChatMessage[]>(queryKey, (prev = []) => {
          const withoutOptimistic = prev.filter((message) => message.id !== context?.optimisticId);
          return [...withoutOptimistic, pair.user, pair.assistant];
        });
      },
    },
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, sendMessageMutation.isPending]);

  const lastUpdated = useMemo(() => {
    if (messages.length === 0) {
      return null;
    }
    return messages[messages.length - 1].createdAt;
  }, [messages]);

  const submitMessage = () => {
    const trimmed = composer.trim();
    if (!trimmed) {
      return;
    }
    sendMessageMutation.mutate({ content: trimmed });
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

  return (
    <section className="flex h-[calc(100vh-9rem)] flex-col gap-6 py-2 text-[color:var(--text-secondary)] transition-colors">
      <header className="surface-panel flex flex-col gap-4 rounded-3xl p-6 shadow-soft sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <Badge
              variant="secondary"
              className="border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] text-[color:var(--text-secondary)]"
            >
              Session
            </Badge>
            <span className="truncate text-sm text-[color:var(--text-muted)]" title={sessionId}>
              {sessionId}
            </span>
          </div>
          <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">Conversation workspace</h1>
          <p className="max-w-2xl text-sm md:text-base">
            Ask questions, iterate on answers, and explore your data sources. Responses are stubbed until you connect
            your chosen model provider.
          </p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <ThemeToggle size="sm" />
          {lastUpdated ? (
            <p className="text-xs text-[color:var(--text-muted)]">Updated {formatRelativeDate(lastUpdated)}</p>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => chatQuery.refetch()} disabled={chatQuery.isFetching}>
            <History className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-6 lg:flex-row">
        <aside className="hidden w-full max-w-xs shrink-0 flex-col gap-4 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-5 text-[color:var(--text-secondary)] shadow-soft lg:flex">
          <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Quick prompts</h2>
          <p className="text-xs text-[color:var(--text-muted)]">Jump-start your conversation with curated suggestions.</p>
          <div className="space-y-2">
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="w-full rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-3 py-2 text-left text-sm text-[color:var(--text-secondary)] transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--chip-bg)] hover:text-[color:var(--text-primary)]"
                onClick={() => applyPrompt(prompt)}
              >
                <Sparkles className="mr-2 inline-block h-4 w-4 text-[color:var(--accent)]" aria-hidden="true" />
                {prompt}
              </button>
            ))}
          </div>
          <div className="mt-auto space-y-3 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4 text-sm">
            <p className="font-medium text-[color:var(--text-primary)]">Connect a model</p>
            <p className="text-[color:var(--text-muted)]">Swap this stub for your preferred LLM endpoint and stream responses in real time.</p>
            <Label htmlFor="model-endpoint" className="text-xs uppercase tracking-wide text-[color:var(--accent)]">
              Endpoint hint
            </Label>
            <Input
              id="model-endpoint"
              value="https://api.your-llm.com/v1/chat"
              readOnly
              className="cursor-text text-xs text-[color:var(--text-secondary)]"
            />
          </div>
        </aside>

        <div className="surface-panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-3xl shadow-soft">
          <div className="flex items-center justify-between border-b border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]/95 px-6 py-4 backdrop-blur">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[color:var(--accent)] text-sm font-semibold text-white">
                LB
              </span>
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">LangBridge Assistant</p>
                <p className="text-xs text-[color:var(--text-muted)]">Stubbed assistant awaiting model integration</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
              onClick={() => {
                if (messages.length === 0) {
                  return;
                }
                const lastUserMessage = [...messages].reverse().find((message) => message.role === 'user');
                if (!lastUserMessage) {
                  toast({
                    title: 'Nothing to regenerate',
                    description: 'Send a prompt before trying to regenerate the response.',
                  });
                  return;
                }
                setComposer(lastUserMessage.content);
              }}
            >
              <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
              Regenerate
            </Button>
          </div>

          <div className="flex min-h-0 flex-1 flex-col">
            <div
              className="flex-1 space-y-4 overflow-y-auto px-6 py-6"
              aria-live="polite"
              aria-label="Conversation transcript"
            >
              {chatQuery.isLoading ? (
                <div className="space-y-4">
                  {Array.from({ length: 4 }).map((_, index) => (
                    <div key={index} className="space-y-3">
                      <Skeleton className="h-4 w-24 bg-[color:var(--surface-muted)]" />
                      <Skeleton className="h-16 w-3/4 bg-[color:var(--surface-muted)]" />
                    </div>
                  ))}
                </div>
              ) : chatQuery.isError ? (
                <div className="rounded-2xl border border-[color:var(--border-strong)] bg-[color:var(--danger-soft)] p-6 text-sm text-[color:var(--text-primary)]">
                  <p className="font-semibold">We hit a snag</p>
                  <p className="mt-2 text-[color:var(--text-muted)]">{(chatQuery.error as Error).message}</p>
                  <Button variant="outline" size="sm" className="mt-4" onClick={() => chatQuery.refetch()}>
                    Try again
                  </Button>
                </div>
              ) : messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
                  <Sparkles className="h-10 w-10 text-[color:var(--accent)]" aria-hidden="true" />
                  <div className="space-y-1">
                    <p className="text-base font-semibold text-[color:var(--text-primary)]">Start the conversation</p>
                    <p className="text-sm text-[color:var(--text-muted)]">
                      Ask a question or use one of the quick prompts to see a stubbed response.
                    </p>
                  </div>
                </div>
              ) : (
                <ol className="space-y-4 text-sm">
                  {messages.map((message) => {
                    if (message.role === 'system') {
                      return (
                        <li key={message.id} className="flex justify-center">
                          <div className="max-w-lg rounded-full border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-2 text-xs text-[color:var(--text-muted)]">
                            {message.content}
                          </div>
                        </li>
                      );
                    }

                    const isUser = message.role === 'user';
                    const bubbleClasses = isUser
                      ? 'bg-[color:var(--accent)] text-white'
                      : 'border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-primary)]';
                    const timestampClasses = isUser ? 'text-white/80' : 'text-[color:var(--text-muted)]';

                    return (
                      <li key={message.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                        <div className="flex max-w-2xl items-end gap-3">
                          {!isUser ? (
                            <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-xs font-semibold text-[color:var(--text-primary)]">
                              LB
                            </span>
                          ) : null}
                          <div className={`rounded-3xl px-4 py-3 shadow-sm transition ${bubbleClasses}`}>
                            <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                            <p className={`mt-2 text-[11px] uppercase tracking-wide ${timestampClasses}`}>
                              {formatRelativeDate(message.createdAt)}
                            </p>
                          </div>
                          {isUser ? (
                            <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-xs font-semibold text-[color:var(--text-secondary)]">
                              You
                            </span>
                          ) : null}
                        </div>
                      </li>
                    );
                  })}
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
                      type="submit"
                      size="lg"
                      isLoading={sendMessageMutation.isPending}
                      loadingText="Sending..."
                      disabled={!composer.trim() || sendMessageMutation.isPending}
                      className="gap-2"
                    >
                      Send
                      <Send className="h-4 w-4" aria-hidden="true" />
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
