'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Sparkles, Send, History, RefreshCw } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { formatRelativeDate } from '@/lib/utils';

import type { ChatMessage, ChatMessagePair } from '../../types';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

function withApi(path: string) {
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE}${path}`;
}

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

  const chatQuery = useQuery<ChatMessage[]>({
    queryKey: ['chat', sessionId],
    queryFn: async () => {
      const response = await fetch(withApi(`/api/v1/chat/sessions/${sessionId}/messages`), {
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || 'Unable to load chat messages');
      }

      return response.json();
    },
    refetchInterval: 8000,
  });

  const messages = chatQuery.data ?? [];

  const sendMessageMutation = useMutation<ChatMessagePair, Error, { content: string }, { snapshot: ChatMessage[]; optimisticId: string }>(
    {
      mutationFn: async ({ content }) => {
        const response = await fetch(withApi(`/api/v1/chat/sessions/${sessionId}/messages`), {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ content }),
        });

        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || 'Unable to send message');
        }

        return response.json();
      },
      onMutate: async ({ content }) => {
        await queryClient.cancelQueries({ queryKey: ['chat', sessionId] });
        const previousMessages = queryClient.getQueryData<ChatMessage[]>(['chat', sessionId]) ?? [];
        const optimisticMessage: ChatMessage = {
          id: `temp-${Date.now()}`,
          sessionId,
          role: 'user',
          content,
          createdAt: new Date().toISOString(),
        };

        queryClient.setQueryData<ChatMessage[]>(['chat', sessionId], [...previousMessages, optimisticMessage]);

        return { snapshot: previousMessages, optimisticId: optimisticMessage.id };
      },
      onError: (error, _variables, context) => {
        queryClient.setQueryData(['chat', sessionId], context?.snapshot ?? []);
        toast({ title: 'Message failed', description: error.message, variant: 'destructive' });
      },
      onSuccess: (pair, _variables, context) => {
        queryClient.setQueryData<ChatMessage[]>(['chat', sessionId], (prev = []) => {
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
    <section className="flex h-[calc(100vh-9rem)] flex-col gap-6 py-2">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <Badge variant="secondary">Session</Badge>
            <span className="truncate text-sm text-slate-500" title={sessionId}>
              {sessionId}
            </span>
          </div>
          <h1 className="text-2xl font-semibold text-slate-900 md:text-3xl">Conversation workspace</h1>
          <p className="max-w-2xl text-sm text-slate-600 md:text-base">
            Ask questions, iterate on answers, and explore your data sources. Responses are stubbed until you connect your
            chosen model provider.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          {lastUpdated ? (
            <p className="text-xs text-slate-500">Updated {formatRelativeDate(lastUpdated)}</p>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => chatQuery.refetch()} disabled={chatQuery.isFetching}>
            <History className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-6 lg:flex-row">
        <aside className="hidden w-full max-w-xs shrink-0 flex-col gap-4 rounded-3xl border border-slate-200 bg-white/70 p-5 shadow-sm lg:flex">
          <h2 className="text-sm font-semibold text-slate-900">Quick prompts</h2>
          <p className="text-xs text-slate-500">Jump-start your conversation with curated suggestions.</p>
          <div className="space-y-2">
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                onClick={() => applyPrompt(prompt)}
              >
                <Sparkles className="mr-2 inline-block h-4 w-4 text-indigo-500" aria-hidden="true" />
                {prompt}
              </button>
            ))}
          </div>
          <div className="mt-auto space-y-3 rounded-2xl border border-indigo-100 bg-indigo-50 p-4 text-sm text-indigo-700">
            <p className="font-medium">Connect a model</p>
            <p>Swap this stub for your preferred LLM endpoint and stream responses in real time.</p>
            <Label htmlFor="model-endpoint" className="text-xs uppercase tracking-wide text-indigo-600">
              Endpoint hint
            </Label>
            <Input id="model-endpoint" value="https://api.your-llm.com/v1/chat" readOnly className="cursor-text text-xs" />
          </div>
        </aside>

        <Card className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-3xl border-0 bg-white shadow-xl shadow-slate-200/70">
          <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                LB
              </span>
              <div>
                <p className="text-sm font-semibold text-slate-900">LangBridge Assistant</p>
                <p className="text-xs text-slate-500">Stubbed assistant awaiting model integration</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
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

          <div className="flex min-h-0 flex-1 flex-col bg-gradient-to-b from-white via-white to-slate-50">
            <div
              className="flex-1 space-y-4 overflow-y-auto px-6 py-6"
              aria-live="polite"
              aria-label="Conversation transcript"
            >
              {chatQuery.isLoading ? (
                <div className="space-y-4">
                  {Array.from({ length: 4 }).map((_, index) => (
                    <div key={index} className="space-y-3">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-16 w-3/4" />
                    </div>
                  ))}
                </div>
              ) : chatQuery.isError ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
                  <p className="font-semibold">We hit a snag</p>
                  <p className="mt-2 text-red-600">{(chatQuery.error as Error).message}</p>
                  <Button variant="outline" size="sm" className="mt-4" onClick={() => chatQuery.refetch()}>
                    Try again
                  </Button>
                </div>
              ) : messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-slate-500">
                  <Sparkles className="h-10 w-10 text-indigo-500" aria-hidden="true" />
                  <div>
                    <p className="text-base font-semibold text-slate-700">Start the conversation</p>
                    <p className="mt-1 text-sm text-slate-500">
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
                          <div className="max-w-lg rounded-full border border-dashed border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-500">
                            {message.content}
                          </div>
                        </li>
                      );
                    }

                    const isUser = message.role === 'user';
                    return (
                      <li key={message.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                        <div className="flex max-w-2xl items-end gap-3">
                          {!isUser ? (
                            <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
                              LB
                            </span>
                          ) : null}
                          <div
                            className={`rounded-3xl px-4 py-3 shadow-sm transition ${
                              isUser
                                ? 'bg-slate-900 text-white'
                                : 'border border-slate-200 bg-white text-slate-800'
                            }`}
                          >
                            <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                            <p className={`mt-2 text-[11px] uppercase tracking-wide ${isUser ? 'text-slate-200' : 'text-slate-400'}`}>
                              {formatRelativeDate(message.createdAt)}
                            </p>
                          </div>
                          {isUser ? (
                            <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-xs font-semibold text-slate-600">
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

            <form onSubmit={handleSubmit} className="border-t border-slate-100 bg-white/80 px-6 py-4">
              <div className="rounded-3xl border border-slate-200 bg-white shadow-sm">
                <Textarea
                  value={composer}
                  onChange={(event) => setComposer(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  placeholder="Shift + Enter for a new line. Describe what you need..."
                  rows={3}
                  className="min-h-[120px] resize-none rounded-3xl border-0 px-5 py-4 text-base focus-visible:ring-0"
                  aria-label="Message LangBridge assistant"
                />
                <div className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap gap-2">
                    {QUICK_PROMPTS.slice(0, 2).map((prompt) => (
                      <Button key={prompt} type="button" size="sm" variant="secondary" onClick={() => applyPrompt(prompt)}>
                        <Sparkles className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
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
                    >
                      Send
                      <Send className="ml-2 h-4 w-4" aria-hidden="true" />
                    </Button>
                  </div>
                </div>
              </div>
            </form>
          </div>
        </Card>
      </div>
    </section>
  );
}
