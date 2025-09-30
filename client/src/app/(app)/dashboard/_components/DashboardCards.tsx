'use client';

import { useCallback, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Database, Bot, MessageSquare, Plus } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { formatRelativeDate } from '@/lib/utils';

import { AddSourceDialog } from './AddSourceDialog';
import { QuickAgentCreateDrawer } from './QuickAgentCreateDrawer';
import type { DataSource, CreateChatResponse } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

function withApiBase(path: string) {
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE}${path}`;
}

export function DashboardCards() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();

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

  const startChatMutation = useMutation<CreateChatResponse, Error>({
    mutationFn: async () => {
      const response = await fetch(withApiBase('/api/v1/chat/sessions'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || 'Failed to start chat session');
      }
      return response.json();
    },
    onSuccess: ({ sessionId }) => {
      toast({ title: 'Chat session created', description: 'Redirecting to your conversation.' });
      router.push(`/chat/${sessionId}`);
    },
    onError: (error) => {
      toast({ title: 'Something went wrong', description: error.message, variant: 'destructive' });
    },
  });

  const recentSources = useMemo(() => sources?.slice(0, 4) ?? [], [sources]);

  const handleSourceCreated = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['datasources'] });
    await refetch();
  }, [queryClient, refetch]);

  const statusVariantMap: Record<DataSource['status'], 'success' | 'destructive' | 'warning' | 'secondary'> = {
    connected: 'success',
    error: 'destructive',
    pending: 'warning',
  };

  const statusLabelMap: Record<DataSource['status'], string> = {
    connected: 'Connected',
    error: 'Error',
    pending: 'Pending',
  };

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <span className="rounded-full bg-slate-900/10 p-2 text-slate-900">
                <Database className="h-5 w-5" aria-hidden="true" />
              </span>
              Add Source
            </CardTitle>
            <CardDescription className="mt-2 max-w-md">
              Connect Snowflake, Postgres, MySQL, or APIs. Use these connections across LangBridge.
            </CardDescription>
          </div>
          <AddSourceDialog onCreated={handleSourceCreated}>
            <Button variant="secondary" size="sm" aria-label="Add source">
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add
            </Button>
          </AddSourceDialog>
        </CardHeader>
        <CardContent>
          <p className="text-sm font-medium text-slate-700">Recent sources</p>
          <div className="mt-4 space-y-4" aria-live="polite">
            {isLoading ? (
              <>
                {Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="space-y-2">
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                ))}
              </>
            ) : isError ? (
              <div className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-600">
                Unable to load data sources.{' '}
                <button
                  type="button"
                  className="font-medium text-slate-900 underline-offset-2 hover:underline"
                  onClick={() => refetch()}
                >
                  Retry
                </button>
              </div>
            ) : recentSources.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-200 p-6 text-sm text-slate-600">
                No data sources yet. Start by adding one above.
              </div>
            ) : (
              <ul className="space-y-3" aria-label="Recent data sources">
                {recentSources.map((source) => (
                  <li key={source.id} className="flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{source.name}</p>
                      <p className="text-xs text-slate-500">{source.type.toUpperCase()} ? {formatRelativeDate(source.createdAt)}</p>
                    </div>
                    <Badge variant={statusVariantMap[source.status]}>{statusLabelMap[source.status]}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <span className="rounded-full bg-indigo-600/10 p-2 text-indigo-600">
                <Bot className="h-5 w-5" aria-hidden="true" />
              </span>
              Build Agent
            </CardTitle>
            <CardDescription className="mt-2 max-w-md">
              Create agentic workflows across your connected sources, or start from templates.
            </CardDescription>
          </div>
          <Button variant="secondary" size="sm" onClick={() => router.push('/agents')} aria-label="Go to agents">
            Manage
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <QuickAgentCreateDrawer
            sources={sources ?? []}
            onCreated={(agentId) => router.push(`/agents/${agentId}`)}
          />
        </CardContent>
        <CardFooter>
          <p className="text-xs text-slate-500">
            Tip: Use templates to kickstart agents optimised for SQL analytics, document Q&A, or hybrid workflows.
          </p>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <span className="rounded-full bg-emerald-600/10 p-2 text-emerald-600">
              <MessageSquare className="h-5 w-5" aria-hidden="true" />
            </span>
            Start New Chat
          </CardTitle>
          <CardDescription className="mt-2 max-w-md">
            Jump into a fresh conversation with LangBridge. Your connected sources power the answers.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button
            size="lg"
            className="w-full"
            onClick={() => startChatMutation.mutate()}
            isLoading={startChatMutation.isPending}
            loadingText="Creating session..."
          >
            Start a new chat
          </Button>
          <Button
            variant="ghost"
            className="w-full"
            onClick={() => router.push('/chat')}
            aria-label="View recent chats"
          >
            View recent chats
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
