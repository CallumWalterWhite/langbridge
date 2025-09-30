import type { ReactNode } from 'react';

import { AppProviders } from './providers';

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AppProviders>
      <div className="min-h-screen bg-slate-50">
        <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 p-6 md:p-10">{children}</main>
      </div>
    </AppProviders>
  );
}
