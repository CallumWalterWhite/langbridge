'use client';

import type { ReactNode } from 'react';

import { ThemeToggle } from '@/components/ThemeToggle';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL!;

export default function Page() {
  const loginUrl = `${BACKEND}/api/v1/auth/login/github`;

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
            Connect your GitHub account to sync repositories, manage language bridges, and pick up right where you left
            off. Authentication stays secure and password-free.
          </p>
        </div>

        <a
          href={loginUrl}
          className="inline-flex w-full items-center justify-center gap-3 rounded-full bg-[color:var(--accent)] px-6 py-3 text-base font-semibold text-white shadow-lg shadow-[rgba(37,99,235,0.25)] transition hover:-translate-y-0.5 hover:bg-[color:var(--accent-strong)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
        >
          <GitHubMark className="h-5 w-5" />
          Continue with GitHub
        </a>

        <div className="grid gap-4 text-sm text-[color:var(--text-secondary)] sm:grid-cols-2">
          <Feature label="No extra passwords">Authenticate using GitHub&apos;s trusted OAuth flow.</Feature>
          <Feature label="Team-ready">Access shared projects in a couple of clicks.</Feature>
          <Feature label="Secure by default">Your data stays encrypted end-to-end.</Feature>
          <Feature label="Quick onboarding">Start translating instantly with smart defaults.</Feature>
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
