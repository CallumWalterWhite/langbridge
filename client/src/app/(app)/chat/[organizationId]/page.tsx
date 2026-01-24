'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, MessageSquare, Plus, RefreshCw, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { formatRelativeDate } from '@/lib/utils';
import { createThread, deleteThread, listThreads } from '@/orchestration/threads';
import type { Thread } from '@/orchestration/threads';

const threadsQueryKey = (organizationId: string) => ['chat-threads', organizationId] as const;

type ChatIndexPageProps = {
  params: { organizationId: string };
};

export default function ChatIndexPage({ params }: ChatIndexPageProps) {
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

  const threadsQuery = useQuery<Thread[]>({
    queryKey: threadsQueryKey(organizationId),
    queryFn: () => listThreads(organizationId),
    enabled: Boolean(organizationId),
  });

  const createThreadMutation = useMutation({
    mutationFn: () => createThread(organizationId),
    onSuccess: (thread) => {
      queryClient.invalidateQueries({ queryKey: threadsQueryKey(organizationId) });
      router.push(`/chat/${organizationId}/${thread.id}`);
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Unable to start a new thread';
      toast({ title: 'Could not create thread', description: message, variant: 'destructive' });
    },
  });

  const deleteThreadMutation = useMutation({
    mutationFn: (threadId: string) => deleteThread(organizationId, threadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: threadsQueryKey(organizationId) });
      toast({ title: 'Thread deleted', description: 'The thread has been removed.' });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Unable to delete this thread';
      toast({ title: 'Could not delete thread', description: message, variant: 'destructive' });
    },
  });

  const handleCreateChat = () => {
    if (createThreadMutation.isPending) {
      return;
    }
    createThreadMutation.mutate();
  };

  const handleDeleteThread = (event: React.MouseEvent<HTMLButtonElement>, threadId: string) => {
    event.preventDefault();
    event.stopPropagation();
    if (deleteThreadMutation.isPending) {
      return;
    }
    deleteThreadMutation.mutate(threadId);
  };

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Threads</p>
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">Your thread workspace</h1>
              <p className="text-sm md:text-base">
                Review recent threads, resume ongoing investigations, or spin up a new agent-led session grounded in your data.
              </p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-end">
            <Button
              onClick={handleCreateChat}
              size="sm"
              className="gap-2"
              disabled={createThreadMutation.isPending}
              isLoading={createThreadMutation.isPending}
              loadingText="Creating..."
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              New thread
            </Button>
          </div>
        </div>
      </header>

      <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Recent threads</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => threadsQuery.refetch()}
            disabled={threadsQuery.isFetching}
            className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
          >
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
          </Button>
        </div>

        <div className="mt-6 flex-1">
          {threadsQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
                  <Skeleton className="h-4 w-32" />
                </div>
              ))}
            </div>
          ) : threadsQuery.isError ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <p className="text-sm">We couldn&apos;t load threads right now.</p>
              <Button onClick={() => threadsQuery.refetch()} variant="outline" size="sm">
                Try again
              </Button>
            </div>
          ) : (threadsQuery.data ?? []).length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
              <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                No history yet
              </div>
              <div className="space-y-2">
                <p className="text-base font-semibold text-[color:var(--text-primary)]">No threads found</p>
                <p className="text-sm">Start a new thread to see it appear here.</p>
              </div>
              <Button onClick={handleCreateChat} size="sm" className="gap-2" disabled={createThreadMutation.isPending}>
                <MessageSquare className="h-4 w-4" aria-hidden="true" />
                Start a thread
              </Button>
            </div>
          ) : (
            <ul className="space-y-3">
              {threadsQuery.data
                ?.slice()
                .sort((a, b) => (a.updatedAt != null && b.updatedAt != null ? a.updatedAt < b.updatedAt ? 1 : -1: 0))
                .map((thread) => {
                  const timestamp = thread.updatedAt ?? thread.createdAt;
                  const timeLabel = thread.title ? 'Updated' : 'Created';

                  return (
                    <li key={thread.id}>
                      <div className="group flex items-center justify-between rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-4 transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-alt)]">
                        <Link
                          href={`/chat/${organizationId}/${thread.id}`}
                          className="flex flex-1 items-center justify-between gap-3"
                        >
                          <div className="flex items-center gap-3">
                            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-sm font-semibold text-[color:var(--text-primary)]">
                              {thread.id.slice(0, 2).toUpperCase()}
                            </span>
                            <div>
                              <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                                {thread.title?.trim() || `Thread ${thread.id.slice(0, 8)}`}
                              </p>
                              <p className="text-xs text-[color:var(--text-muted)]">
                                {timeLabel} {timestamp ? formatRelativeDate(timestamp) : 'just now'}
                              </p>
                            </div>
                          </div>
                          <ArrowRight className="h-4 w-4 text-[color:var(--text-muted)] transition group-hover:translate-x-1 group-hover:text-[color:var(--text-primary)]" aria-hidden="true" />
                        </Link>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                          onClick={(event) => handleDeleteThread(event, thread.id)}
                          disabled={deleteThreadMutation.isPending}
                          aria-label={`Delete thread ${thread.id.slice(0, 8)}`}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </div>
                    </li>
                  );
                })}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
