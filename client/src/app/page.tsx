'use client';

import type { ReactNode } from 'react';

import { ThemeToggle } from '@/components/ThemeToggle';
import { cn } from '@/lib/utils';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

const AUTH_PROVIDERS = [
  {
    id: 'github',
    label: 'Continue with GitHub',
    description: 'Use your GitHub identity to sync repos and automations.',
    className:
      'bg-[color:var(--accent)] text-white shadow-lg shadow-[rgba(37,99,235,0.25)] hover:bg-[color:var(--accent-strong)]',
    iconClassName: 'text-white',
    Icon: GitHubMark,
  },
  {
    id: 'google',
    label: 'Continue with Google',
    description: 'Sign in with Google Workspace or personal accounts.',
    className:
      'border border-[color:var(--panel-border)] bg-white text-slate-900 shadow-sm hover:bg-slate-100 dark:bg-[color:var(--panel-alt)] dark:text-[color:var(--text-primary)]',
    iconClassName: '',
    Icon: GoogleMark,
  },
];

export default function Page() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[color:var(--shell-bg)] px-6 py-16 text-[color:var(--text-primary)] transition-colors">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-[radial-gradient(circle_at_top,_var(--accent-soft),_transparent_60%)]" />
      <div className="pointer-events-none absolute inset-y-0 right-[-20%] -z-10 hidden aspect-square w-[36rem] rounded-full bg-[radial-gradient(circle,_var(--accent-soft)_0%,_transparent_70%)] blur-3xl lg:block" />

      <ThemeToggle className="absolute right-6 top-6" size="sm" />

      <section className="relative w-full max-w-2xl space-y-8 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-10 shadow-soft backdrop-blur">
        <div className="inline-flex items-center gap-2 rounded-full bg-[color:var(--chip-bg)] px-4 py-2 text-sm text-[color:var(--text-secondary)]">
          <span className="flex h-2 w-2 items-center justify-center rounded-full bg-emerald-400" />
          <span>LangBridge access portal</span>
        </div>

        <div className="space-y-4">
          <h1 className="text-4xl font-semibold tracking-tight">Sign in to continue</h1>
          <p className="text-base leading-relaxed text-[color:var(--text-secondary)]">
            Choose the workspace identity that works best for you. Authenticate with GitHub for code-first flows or
            Google to plug in your Workspace teams—no extra passwords required.
          </p>
        </div>

        <div className="space-y-3">
          {AUTH_PROVIDERS.map(({ id, label, Icon, className, iconClassName, description }) => {
            const loginHref = `${BACKEND}/api/v1/auth/login/${id}`;
            return (
              <a
                key={id}
                href={loginHref}
                className={cn(
                  'inline-flex w-full items-center justify-between gap-3 rounded-full px-6 py-3 text-base font-semibold transition hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]',
                  className,
                )}
              >
                <div className="flex w-full flex-col gap-1">
                  <span className="flex items-center gap-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/10">
                      <Icon className={cn('h-5 w-5', iconClassName)} />
                    </span>
                    {label}
                  </span>
                  <span className="text-xs text-[color:var(--text-secondary)]">{description}</span>
                </div>
                <span aria-hidden className="text-sm text-[color:var(--text-secondary)]">
                  ↗
                </span>
              </a>
            );
          })}
        </div>

        <div className="grid gap-4 text-sm text-[color:var(--text-secondary)] sm:grid-cols-2">
          <Feature label="No extra passwords">Authenticate through GitHub or Google—your choice.</Feature>
          <Feature label="Team-ready">Access shared organizations and projects instantly.</Feature>
          <Feature label="Secure by default">Session cookies stay encrypted and scoped to your workspace.</Feature>
          <Feature label="Quick onboarding">Sign in once and jump back into your agents and analytics.</Feature>
        </div>

        <p className="text-center text-xs text-[color:var(--text-muted)]">
          By continuing, you agree to our terms and acknowledge the privacy policy.
        </p>
      </section>
    </main>
  );
}

function Feature({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] px-4 py-3 text-[color:var(--text-secondary)] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
      <p className="font-medium text-[color:var(--text-primary)]">{label}</p>
      <p className="mt-1 text-xs text-[color:var(--text-muted)]">{children}</p>
    </div>
  );
}

function GitHubMark({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className={className}
      role="img"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        fill="currentColor"
        d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2c-3.34.73-4-1.61-4-1.61a3.1 3.1 0 0 0-1.34-1.72c-1.09-.75.08-.74.08-.74a2.45 2.45 0 0 1 1.78 1.2 2.5 2.5 0 0 0 3.42 1 2.52 2.52 0 0 1 .75-1.57c-2.67-.31-5.47-1.35-5.47-6a4.72 4.72 0 0 1 1.26-3.28 4.37 4.37 0 0 1 .12-3.24s1-.33 3.3 1.25a11.38 11.38 0 0 1 6 0c2.29-1.58 3.29-1.25 3.29-1.25a4.36 4.36 0 0 1 .12 3.24 4.71 4.71 0 0 1 1.25 3.28c0 4.64-2.81 5.64-5.49 5.94a2.83 2.83 0 0 1 .81 2.2v3.26c0 .32.22.7.83.58A12 12 0 0 0 12 .5Z"
      />
    </svg>
  );
}

function GoogleMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={className} role="img" xmlns="http://www.w3.org/2000/svg">
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.85-.07-1.47-.22-2.12H12v3.83h6.57c-.13 1.06-.83 2.66-2.38 3.73l-.02.15 3.46 2.69.24.02c2.23-2.06 3.52-5.09 3.52-8.3Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.18 0 5.85-1.04 7.8-2.84l-3.72-2.89c-.99.69-2.32 1.18-4.08 1.18a7.08 7.08 0 0 1-6.7-4.84l-.14.01-3.64 2.81-.05.13C3.46 21.53 7.37 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.3 14.61a7.03 7.03 0 0 1-.39-2.27c0-.79.14-1.56.37-2.27l-.01-.15L1.58 7.04l-.12.06A11.96 11.96 0 0 0 0 12.34a11.96 11.96 0 0 0 1.47 5.24l3.83-2.97Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.73c2.22 0 3.72.96 4.58 1.76l3.34-3.26C17.82 1.21 15.18 0 12 0 7.37 0 3.46 2.47 1.47 6.1l3.81 2.93c.92-2.74 3.44-4.3 6.72-4.3Z"
      />
    </svg>
  );
}
