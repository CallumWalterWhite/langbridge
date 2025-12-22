'use client';

import Link from 'next/link';
import { JSX } from 'react';

import { Button } from '@/components/ui/button';

export default function SettingsPage(): JSX.Element {
  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
            User settings
          </p>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
              Manage your preferences
            </h1>
            <p className="text-sm md:text-base">
              Personal settings, notifications, and auth preferences will live here.
            </p>
          </div>
        </div>
      </header>

      <section className="surface-panel rounded-3xl p-6 shadow-soft">
        <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Coming soon</h2>
        <p className="mt-2 text-sm">
          Organization settings now live under each organization workspace.
        </p>
        <div className="mt-4">
          <Button asChild variant="outline" size="sm">
            <Link href="/organizations">Go to organizations</Link>
          </Button>
        </div>
      </section>
    </div>
  );
}
