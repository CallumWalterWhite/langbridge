'use client';

import * as React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { QueryClientConfig } from '@tanstack/react-query';

import { ToastProvider } from '@/components/ui/toast';
import { WorkspaceScopeProvider } from '@/context/workspaceScope';

const queryClientConfig: QueryClientConfig = {
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30_000,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
};

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(() => new QueryClient(queryClientConfig));

  return (
    <QueryClientProvider client={queryClient}>
      <WorkspaceScopeProvider>
        <ToastProvider>{children}</ToastProvider>
      </WorkspaceScopeProvider>
    </QueryClientProvider>
  );
}

