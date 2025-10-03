'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, MessageSquare, Plus, RefreshCw } from 'lucide-react';

import { ThemeToggle } from '@/components/ThemeToggle';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { formatRelativeDate } from '@/lib/utils';
import { createChatSession, listChatSessions } from '@/orchestration/chat';
import type { ChatSession } from '@/orchestration/chat';

const sessionsQueryKey = ['chat-sessions'] as const;

export default function ChatIndexPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const sessionsQuery = useQuery<ChatSession[]>({
    queryKey: sessionsQueryKey,
    queryFn: () => listChatSessions(),
  });

  const createSessionMutation = useMutation({
    mutationFn: () => createChatSession(),
    onSuccess: ({ sessionId }) => {
      queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
      router.push(`/chat/${sessionId}`);
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Unable to start a new chat';
      toast({ title: 'Could not create chat', description: message, variant: 'destructive' });
    },
  });

  const handleCreateChat = () => {
    if (createSessionMutation.isPending) {
      return;
    }
    createSessionMutation.mutate();
  };

  return (
    <div className="flex min-h-full flex-col gap-6 px-6 py-10 text-[color:var(--text-secondary)] transition-colors sm:px-10 lg:px-14">
      <header className="surface-panel flex flex-col gap-4 rounded-3xl p-6 shadow-soft sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Conversations</p>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">Your chat workspace</h1>
            <p className="text-sm md:text-base">
              Review recent sessions, resume ongoing investigations, or spin up a new assistant conversation grounded in
              your connected data sources.
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-3 sm:flex-row sm:items-center">
          <ThemeToggle size="sm" className="sm:order-2" />
          <Button
            onClick={handleCreateChat}
            size="sm"
            className="gap-2 sm:order-1"
            disabled={createSessionMutation.isPending}
            isLoading={createSessionMutation.isPending}
            loadingText="Creating..."
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            New conversation
          </Button>
        </div>
      </header>

      <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Recent sessions</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => sessionsQuery.refetch()}
            disabled={sessionsQuery.isFetching}
            className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
          >
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
          </Button>
        </div>

        <div className="mt-6 flex-1">
          {sessionsQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
                  <Skeleton className="h-4 w-32" />
                </div>
              ))}
            </div>
          ) : sessionsQuery.isError ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <p className="text-sm">We couldn&apos;t load conversations right now.</p>
              <Button onClick={() => sessionsQuery.refetch()} variant="outline" size="sm">
                Try again
              </Button>
            </div>
          ) : (sessionsQuery.data ?? []).length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                No history yet
              </div>
              <div className="space-y-2">
                <p className="text-base font-semibold text-[color:var(--text-primary)]">No conversations found</p>
                <p className="text-sm">Start a new chat to see it appear here.</p>
              </div>
              <Button onClick={handleCreateChat} size="sm" className="gap-2" disabled={createSessionMutation.isPending}>
                <MessageSquare className="h-4 w-4" aria-hidden="true" />
                Start talking
              </Button>
            </div>
          ) : (
            <ul className="space-y-3">
              {sessionsQuery.data
                ?.slice()
                .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
                .map((session) => (
                  <li key={session.id}>
                    <Link
                      href={`/chat/${session.id}`}
                      className="group flex items-center justify-between rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-4 transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-alt)]"
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-sm font-semibold text-[color:var(--text-primary)]">
                          {session.id.slice(0, 2).toUpperCase()}
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-[color:var(--text-primary)]">Session {session.id.slice(0, 8)}</p>
                          <p className="text-xs text-[color:var(--text-muted)]">Created {formatRelativeDate(session.createdAt)}</p>
                        </div>
                      </div>
                      <ArrowRight className="h-4 w-4 text-[color:var(--text-muted)] transition group-hover:translate-x-1 group-hover:text-[color:var(--text-primary)]" aria-hidden="true" />
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
