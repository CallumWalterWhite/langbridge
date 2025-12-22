'use client';

import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';

import { Spinner } from '@/components/ui/spinner';
import { fetchSession } from '@/orchestration/auth';

const sessionQueryKey = ['session'] as const;

type AuthGuardProps = {
  children: ReactNode;
};

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const sessionQuery = useQuery({
    queryKey: sessionQueryKey,
    queryFn: fetchSession,
    retry: false,
  });

  const sessionToken = sessionQuery.data?.user?.sub?.trim() ?? '';
  const isAuthenticated = Boolean(sessionToken);

  useEffect(() => {
    if (sessionQuery.isLoading) {
      return;
    }
    if (!isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, router, sessionQuery.isLoading]);

  if (sessionQuery.isLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[color:var(--shell-bg)] text-[color:var(--text-secondary)]">
        <Spinner className="h-6 w-6" />
        <p className="text-sm">{sessionQuery.isLoading ? 'Checking session...' : 'Redirecting to sign in...'}</p>
      </div>
    );
  }

  return children;
}
