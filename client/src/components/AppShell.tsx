'use client';

import { useMemo, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { LogoutButton } from '@/components/LogoutButton';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { useWorkspaceScope } from '@/context/workspaceScope';

interface NavItem {
  href: string;
  label: string;
  description: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    href: '/dashboard',
    label: 'Agentic workspace',
    description: 'Monitor automations and jump back into active orchestrations.',
  },
  {
    href: '/datasources',
    label: 'Data connections',
    description: 'Manage structured connectors and retrievers powering your agents.',
  },
  {
    href: '/agents',
    label: 'LLM connections',
    description: 'Register provider credentials for upcoming agent builders.',
  },
  {
    href: '/organizations',
    label: 'Organizations & projects',
    description: 'Group teammates and resources into collaborative workspaces.',
  },
  {
    href: '/chat',
    label: 'Conversations',
    description: 'Revisit copilot chats and escalate threads to playbooks.',
  },
  {
    href: '/settings',
    label: 'Settings',
    description: 'Adjust workspace preferences, tokens, and audit options.',
  },
];

export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const pathname = usePathname();
  const router = useRouter();
  const { selectedOrganization, selectedProject } = useWorkspaceScope();

  const activeNav =
    NAV_ITEMS.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`)) ?? NAV_ITEMS[0];

  const scopeSummary = useMemo(() => {
    if (!selectedOrganization) {
      return null;
    }
    if (selectedProject) {
      return `${selectedOrganization.name} · ${selectedProject.name}`;
    }
    return selectedOrganization.name;
  }, [selectedOrganization, selectedProject]);

  return (
    <div className="min-h-screen bg-[color:var(--shell-bg)] text-[color:var(--text-primary)] transition-colors">
      <div className="flex min-h-screen flex-col lg:flex-row">
        <aside className="hidden w-72 flex-shrink-0 flex-col border-r border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-5 py-6 text-sm text-[color:var(--text-secondary)] shadow-soft lg:flex">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-full border border-[color:var(--border-strong)] bg-[color:var(--panel-alt)] px-4 py-2 text-sm font-semibold text-[color:var(--text-primary)] transition hover:border-[color:var(--border-strong-hover)] hover:text-[color:var(--text-primary)]"
          >
            LangBridge
          </Link>
          <nav className="mt-8 space-y-1">
            {NAV_ITEMS.map((item) => {
              const isActive = item.href === activeNav.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'block rounded-lg px-3 py-2 transition hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]',
                    isActive
                      ? 'border border-[color:var(--border-strong)] bg-[color:var(--panel-alt)] font-medium text-[color:var(--text-primary)]'
                      : 'text-[color:var(--text-secondary)]',
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto space-y-3 text-xs text-[color:var(--text-muted)]">
            <Link href="/docs" className="inline-flex items-center gap-2 transition hover:text-[color:var(--text-primary)]">
              Documentation
            </Link>
            <Link
              href="/support"
              className="inline-flex items-center gap-2 transition hover:text-[color:var(--text-primary)]"
            >
              Support & feedback
            </Link>
          </div>
        </aside>

        <div className="flex flex-1 flex-col">
          <header className="border-b border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-6 py-4 shadow-soft backdrop-blur">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <h1 className="text-lg font-semibold text-[color:var(--text-primary)]">{activeNav.label}</h1>
                <p className="text-sm text-[color:var(--text-secondary)]">{activeNav.description}</p>
                {scopeSummary ? (
                  <p className="text-xs text-[color:var(--text-muted)]">Scope: {scopeSummary}</p>
                ) : null}
              </div>
              <div className="flex w-full flex-col items-stretch gap-3 sm:w-auto sm:flex-row sm:items-center sm:justify-end">
                <ScopeSelector />
                <div className="inline-flex items-center justify-end gap-3">
                  <ThemeToggle size="sm" />
                  <LogoutButton />
                  <Button variant="outline" size="sm" onClick={() => router.push('/docs/whats-new')}>
                    What&apos;s new
                  </Button>
                </div>
              </div>
            </div>

            <nav className="mt-4 flex gap-2 overflow-x-auto text-sm lg:hidden">
              {NAV_ITEMS.map((item) => {
                const isActive = item.href === activeNav.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'whitespace-nowrap rounded-full px-3 py-1 transition',
                      isActive
                        ? 'border border-[color:var(--border-strong)] bg-[color:var(--panel-alt)] text-[color:var(--text-primary)]'
                        : 'border border-transparent text-[color:var(--text-secondary)] hover:border-[color:var(--panel-border)] hover:text-[color:var(--text-primary)]',
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </header>

          <div className="flex-1 overflow-y-auto">
            <main className="mx-auto w-full max-w-6xl px-6 py-8">{children}</main>
          </div>
        </div>
      </div>
    </div>
  );
}

function ScopeSelector(): JSX.Element {
  const {
    organizations,
    loading,
    error,
    selectedOrganizationId,
    selectedProjectId,
    selectedOrganization,
    setSelectedOrganizationId,
    setSelectedProjectId,
  } = useWorkspaceScope();

  const projectOptions = useMemo(() => selectedOrganization?.projects ?? [], [selectedOrganization]);

  const organizationDisabled = loading || organizations.length === 0;
  const projectDisabled = loading || !selectedOrganization || projectOptions.length === 0;

  return (
    <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-end sm:gap-4">
      <div className="flex min-w-[200px] flex-col gap-1">
        <span className="text-xs font-medium text-[color:var(--text-muted)]">Organization</span>
        <Select
          value={selectedOrganizationId}
          onChange={(event) => setSelectedOrganizationId(event.target.value)}
          disabled={organizationDisabled}
          placeholder={loading ? 'Loading organizations...' : 'Select an organization'}
        >
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>
              {organization.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="flex min-w-[200px] flex-col gap-1">
        <span className="text-xs font-medium text-[color:var(--text-muted)]">Project</span>
        <Select
          value={selectedProjectId}
          onChange={(event) => setSelectedProjectId(event.target.value)}
          disabled={projectDisabled}
          placeholder={
            !selectedOrganizationId
              ? 'Select an organization first'
              : projectOptions.length === 0
                ? 'No projects yet'
                : 'Select a project'
          }
        >
          {selectedOrganizationId ? (
            <option value="">
              All projects{selectedOrganization ? ` · ${selectedOrganization.name}` : ''}
            </option>
          ) : null}
          {projectOptions.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </Select>
      </div>
      {error ? <span className="text-xs text-rose-500">Unable to load organizations.</span> : null}
    </div>
  );
}
