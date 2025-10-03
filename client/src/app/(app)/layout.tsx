import type { ReactNode } from 'react';

import { AppProviders } from './providers';

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AppProviders>
      <div className="min-h-screen bg-[color:var(--shell-bg)] text-[color:var(--text-primary)] transition-colors">
        <main className="mx-auto flex w-full flex-col">{children}</main>
      </div>
    </AppProviders>
  );
}
