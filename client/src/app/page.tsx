'use client';

import * as React from 'react';
import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';

import { ThemeToggle } from '@/components/ThemeToggle';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

function withApiBase(path: string) {
  if (!BACKEND) {
    return path;
  }
  return `${BACKEND}${path}`;
}

const AUTH_PROVIDERS = [
  {
    id: 'github',
    label: 'Continue with GitHub',
    description: 'Use your GitHub identity to sync repos and automations.',
    className:
      'bg-[color:var(--accent)] text-white shadow-soft hover:bg-[color:var(--accent-strong)]',
    iconClassName: 'text-white',
    Icon: GitHubMark,
  },
  {
    id: 'google',
    label: 'Continue with Google',
    description: 'Sign in with Google Workspace or personal accounts.',
    className:
      'border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-primary)] shadow-soft hover:bg-[color:var(--panel-alt)]',
    iconClassName: '',
    Icon: GoogleMark,
  },
];

type NativeFormState = {
  email: string;
  password: string;
  username?: string;
  error: string | null;
  isSubmitting: boolean;
};

async function resolveAuthError(response: Response, fallback: string) {
  const text = await response.text();
  if (!text) {
    return fallback;
  }
  try {
    const payload = JSON.parse(text) as { detail?: string; message?: string };
    return payload.detail ?? payload.message ?? text;
  } catch {
    return text;
  }
}

export default function Page() {
  const router = useRouter();
  const [loginState, setLoginState] = React.useState<NativeFormState>({
    email: '',
    password: '',
    error: null,
    isSubmitting: false,
  });
  const [registerState, setRegisterState] = React.useState<NativeFormState>({
    email: '',
    password: '',
    username: '',
    error: null,
    isSubmitting: false,
  });

  const handleLoginSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const email = loginState.email.trim();
    const password = loginState.password;

    if (!email || !password) {
      setLoginState((prev) => ({ ...prev, error: 'Email and password are required.' }));
      return;
    }

    setLoginState((prev) => ({ ...prev, error: null, isSubmitting: true }));
    try {
      const response = await fetch(withApiBase('/api/v1/auth/login'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        throw new Error(await resolveAuthError(response, 'Unable to sign in.'));
      }
      router.push('/dashboard');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to sign in.';
      setLoginState((prev) => ({ ...prev, error: message }));
    } finally {
      setLoginState((prev) => ({ ...prev, isSubmitting: false }));
    }
  };

  const handleRegisterSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const email = registerState.email.trim();
    const password = registerState.password;
    const username = registerState.username?.trim() || undefined;

    if (!email || !password) {
      setRegisterState((prev) => ({ ...prev, error: 'Email and password are required.' }));
      return;
    }

    if (password.length < 8) {
      setRegisterState((prev) => ({ ...prev, error: 'Password must be at least 8 characters.' }));
      return;
    }

    setRegisterState((prev) => ({ ...prev, error: null, isSubmitting: true }));
    try {
      const payload: { email: string; password: string; username?: string } = { email, password };
      if (username) {
        payload.username = username;
      }
      const response = await fetch(withApiBase('/api/v1/auth/register'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(await resolveAuthError(response, 'Unable to create account.'));
      }
      router.push('/dashboard');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to create account.';
      setRegisterState((prev) => ({ ...prev, error: message }));
    } finally {
      setRegisterState((prev) => ({ ...prev, isSubmitting: false }));
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[color:var(--shell-bg)] px-6 py-16 text-[color:var(--text-primary)] transition-colors">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-[radial-gradient(circle_at_top,_var(--accent-soft),_transparent_60%)]" />
      <div className="pointer-events-none absolute inset-y-0 right-[-20%] -z-10 hidden aspect-square w-[36rem] rounded-full bg-[radial-gradient(circle,_var(--accent-soft)_0%,_transparent_70%)] blur-3xl lg:block" />

      <ThemeToggle className="absolute right-6 top-6" size="sm" />

      <section className="relative w-full max-w-2xl space-y-8 rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-10 shadow-soft backdrop-blur">
        <div className="inline-flex items-center gap-2 rounded-full bg-[color:var(--chip-bg)] px-4 py-2 text-sm text-[color:var(--text-secondary)]">
          <span className="flex h-2 w-2 items-center justify-center rounded-full bg-[color:var(--accent)]" />
          <span>LangBridge access portal</span>
        </div>

        <div className="space-y-4">
          <h1 className="text-4xl font-semibold tracking-tight">Sign in to continue</h1>
          <p className="text-base leading-relaxed text-[color:var(--text-secondary)]">
            Start with SSO for the fastest setup, or use email below for a local account.
          </p>
        </div>

        <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Single sign-on</p>
            <span className="text-xs text-[color:var(--text-muted)]">GitHub + Google</span>
          </div>
          <div className="mt-4 space-y-3">
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
                    -&gt;
                  </span>
                </a>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
          <span className="h-px flex-1 bg-[color:var(--panel-border)]" />
          <span>or use email</span>
          <span className="h-px flex-1 bg-[color:var(--panel-border)]" />
        </div>

        <Tabs defaultValue="sign-in" className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-6 shadow-soft">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Email access</p>
            <h2 className="text-lg font-semibold">Sign in or create an account</h2>
            <p className="text-sm text-[color:var(--text-secondary)]">
              Prefer passwords? Use email to access your workspace.
            </p>
          </div>

          <TabsContent value="sign-in">
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="login-email">Email</Label>
                <Input
                  id="login-email"
                  type="email"
                  value={loginState.email}
                  autoComplete="email"
                  onChange={(event) => setLoginState((prev) => ({ ...prev, email: event.target.value }))}
                  placeholder="you@company.com"
                  required
                  disabled={loginState.isSubmitting}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="login-password">Password</Label>
                <Input
                  id="login-password"
                  type="password"
                  value={loginState.password}
                  autoComplete="current-password"
                  onChange={(event) => setLoginState((prev) => ({ ...prev, password: event.target.value }))}
                  placeholder="********"
                  required
                  disabled={loginState.isSubmitting}
                />
              </div>
              {loginState.error ? (
                <p className="text-sm text-rose-500" role="alert">
                  {loginState.error}
                </p>
              ) : null}
              <Button type="submit" size="lg" className="w-full" isLoading={loginState.isSubmitting} loadingText="Signing in...">
                Sign in
              </Button>
            </form>
          </TabsContent>

          <TabsContent value="create">
            <form onSubmit={handleRegisterSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="register-email">Email</Label>
                <Input
                  id="register-email"
                  type="email"
                  value={registerState.email}
                  autoComplete="email"
                  onChange={(event) => setRegisterState((prev) => ({ ...prev, email: event.target.value }))}
                  placeholder="you@company.com"
                  required
                  disabled={registerState.isSubmitting}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="register-username">Workspace handle (optional)</Label>
                <Input
                  id="register-username"
                  type="text"
                  value={registerState.username ?? ''}
                  autoComplete="username"
                  onChange={(event) => setRegisterState((prev) => ({ ...prev, username: event.target.value }))}
                  placeholder="jordan"
                  disabled={registerState.isSubmitting}
                />
                <p className="text-xs text-[color:var(--text-muted)]">
                  Leave this blank and we will generate one from your email.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="register-password">Password</Label>
                <Input
                  id="register-password"
                  type="password"
                  value={registerState.password}
                  autoComplete="new-password"
                  onChange={(event) => setRegisterState((prev) => ({ ...prev, password: event.target.value }))}
                  placeholder="At least 8 characters"
                  minLength={8}
                  required
                  disabled={registerState.isSubmitting}
                />
              </div>
              {registerState.error ? (
                <p className="text-sm text-rose-500" role="alert">
                  {registerState.error}
                </p>
              ) : null}
              <Button type="submit" size="lg" className="w-full" isLoading={registerState.isSubmitting} loadingText="Creating...">
                Create account
              </Button>
            </form>
          </TabsContent>

          <div className="mt-6 flex flex-col gap-3 border-t border-[color:var(--panel-border)] pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Email options</p>
            <TabsList className="w-full justify-between sm:w-auto sm:justify-start">
              <TabsTrigger value="sign-in" className="flex-1 sm:min-w-[140px]">
                Sign in
              </TabsTrigger>
              <TabsTrigger value="create" className="flex-1 sm:min-w-[140px]">
                Sign up
              </TabsTrigger>
            </TabsList>
          </div>
        </Tabs>

        <div className="grid gap-4 text-sm text-[color:var(--text-secondary)] sm:grid-cols-2">
          <Feature label="Flexible access">Use email credentials or sign in with SSO providers.</Feature>
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
