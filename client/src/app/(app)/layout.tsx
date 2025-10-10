import type { ReactNode } from 'react';

import { AppShell } from '@/components/AppShell';

import { AppProviders } from './providers';

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AppProviders>
      <AppShell>{children}</AppShell>
    </AppProviders>
  );
}
