'use client';

import Link from 'next/link';
import { JSX, useCallback, useMemo, useState } from 'react';
import { ArrowRight, Building2, Folder, RefreshCw, Settings2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { ApiError } from '@/orchestration/http';
import { createOrganization } from '@/orchestration/organizations';

type ProjectListItem = {
  id: string;
  name: string;
  organizationId: string;
  organizationName: string;
};

function resolveErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

export default function OrganizationsPage(): JSX.Element {
  const { toast } = useToast();
  const [newOrganizationName, setNewOrganizationName] = useState('');
  const [creatingOrganization, setCreatingOrganization] = useState(false);
  const {
    organizations,
    loading,
    error,
    selectedOrganizationId,
    selectedProjectId,
    selectedOrganization,
    setSelectedOrganizationId,
    setSelectedProjectId,
    refreshOrganizations,
  } = useWorkspaceScope();

  const organizationList = useMemo(
    () => organizations.slice().sort((a, b) => a.name.localeCompare(b.name)),
    [organizations],
  );

  const projectList = useMemo<ProjectListItem[]>(() => {
    if (selectedOrganization) {
      return selectedOrganization.projects
        .map((project) => ({
          ...project,
          organizationName: selectedOrganization.name,
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
    }

    return organizations
      .flatMap((organization) =>
        organization.projects.map((project) => ({
          ...project,
          organizationName: organization.name,
        })),
      )
      .sort((a, b) => {
        const orgCompare = a.organizationName.localeCompare(b.organizationName);
        if (orgCompare !== 0) {
          return orgCompare;
        }
        return a.name.localeCompare(b.name);
      });
  }, [organizations, selectedOrganization]);

  const handleProjectActivate = useCallback(
    (organizationId: string, projectId: string) => {
      setSelectedOrganizationId(organizationId);
      setSelectedProjectId(projectId);
    },
    [setSelectedOrganizationId, setSelectedProjectId],
  );

  const handleCreateOrganization = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const trimmedName = newOrganizationName.trim();
      if (!trimmedName) {
        toast({
          title: 'Organization name required',
          description: 'Add a name to create a new organization.',
          variant: 'destructive',
        });
        return;
      }
      setCreatingOrganization(true);
      try {
        await createOrganization({ name: trimmedName });
        setNewOrganizationName('');
        toast({
          title: 'Organization created',
          description: `"${trimmedName}" is ready to configure.`,
        });
        await refreshOrganizations();
      } catch (error) {
        toast({
          title: 'Unable to create organization',
          description: resolveErrorMessage(error),
          variant: 'destructive',
        });
      } finally {
        setCreatingOrganization(false);
      }
    },
    [newOrganizationName, refreshOrganizations, toast],
  );

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
              Organizations and projects
            </p>
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
                Shape collaborative workspaces
              </h1>
              <p className="text-sm md:text-base">
                Review every organization and project you can access, then jump into detailed settings for edits and
                scope changes.
              </p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-end">
            <Button asChild size="sm" className="gap-2">
              <Link href="/settings">
                <Settings2 className="h-4 w-4" aria-hidden="true" />
                User settings
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <section className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">New organization</h2>
            <p className="text-sm">
              Spin up a fresh workspace to manage projects, teammates, and environment settings.
            </p>
          </div>
          <form onSubmit={handleCreateOrganization} className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <label className="sr-only" htmlFor="new-organization-name">
              Organization name
            </label>
            <Input
              id="new-organization-name"
              value={newOrganizationName}
              onChange={(event) => setNewOrganizationName(event.target.value)}
              placeholder="Acme Labs"
              className="min-w-[220px]"
              autoComplete="off"
              disabled={creatingOrganization}
            />
            <Button type="submit" size="sm" isLoading={creatingOrganization}>
              Create
            </Button>
          </form>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Organizations</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refreshOrganizations()}
              disabled={loading}
              className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
            >
              <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
            </Button>
          </div>

          <div className="mt-6 flex-1">
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={index}
                    className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                  >
                    <Skeleton className="h-4 w-32" />
                  </div>
                ))}
              </div>
            ) : error ? (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
                <p className="text-sm">We couldn&apos;t load organizations right now.</p>
                <Button onClick={() => refreshOrganizations()} variant="outline" size="sm">
                  Try again
                </Button>
              </div>
            ) : organizationList.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
                <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                  No organizations yet
                </div>
                <div className="space-y-2">
                  <p className="text-base font-semibold text-[color:var(--text-primary)]">No workspaces found</p>
                  <p className="text-sm">Create an organization in settings to start collaborating.</p>
                </div>
              </div>
            ) : (
              <ul className="space-y-3">
                {organizationList.map((organization) => {
                  const isActive = organization.id === selectedOrganizationId;
                  return (
                    <li key={organization.id}>
                      <Link
                        href={`/organizations/${organization.id}`}
                        className="group flex items-center justify-between rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-4 transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--panel-alt)]"
                      >
                        <div className="flex items-center gap-3">
                          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-sm font-semibold text-[color:var(--text-primary)]">
                            <Building2 className="h-4 w-4" aria-hidden="true" />
                          </span>
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold text-[color:var(--text-primary)]">
                                {organization.name}
                              </p>
                              {isActive ? <Badge variant="secondary">Active</Badge> : null}
                            </div>
                            <p className="text-xs text-[color:var(--text-muted)]">
                              {organization.memberCount} member{organization.memberCount === 1 ? '' : 's'} ·{' '}
                              {organization.projects.length} project{organization.projects.length === 1 ? '' : 's'}
                            </p>
                          </div>
                        </div>
                        <ArrowRight
                          className="h-4 w-4 text-[color:var(--text-muted)] transition group-hover:translate-x-1 group-hover:text-[color:var(--text-primary)]"
                          aria-hidden="true"
                        />
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Projects</h2>
              <p className="text-xs text-[color:var(--text-muted)]">
                {selectedOrganization ? `Projects in ${selectedOrganization.name}` : 'All projects'}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refreshOrganizations()}
              disabled={loading}
              className="text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
            >
              <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" /> Refresh
            </Button>
          </div>

          <div className="mt-6 flex-1">
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={index}
                    className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                  >
                    <Skeleton className="h-4 w-32" />
                  </div>
                ))}
              </div>
            ) : error ? (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
                <p className="text-sm">We couldn&apos;t load projects right now.</p>
                <Button onClick={() => refreshOrganizations()} variant="outline" size="sm">
                  Try again
                </Button>
              </div>
            ) : projectList.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
                <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                  No projects yet
                </div>
                <div className="space-y-2">
                  <p className="text-base font-semibold text-[color:var(--text-primary)]">No projects available</p>
                  <p className="text-sm">Create a project in settings to scope new work.</p>
                </div>
              </div>
            ) : (
              <ul className="space-y-3">
                {projectList.map((project) => {
                  const isActive = project.id === selectedProjectId;
                  return (
                    <li
                      key={project.id}
                      className="flex items-center justify-between rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-4 py-4"
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--chip-bg)] text-sm font-semibold text-[color:var(--text-primary)]">
                          <Folder className="h-4 w-4" aria-hidden="true" />
                        </span>
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-[color:var(--text-primary)]">{project.name}</p>
                            {isActive ? <Badge variant="secondary">Active</Badge> : null}
                          </div>
                          <p className="text-xs text-[color:var(--text-muted)]">{project.organizationName}</p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleProjectActivate(project.organizationId, project.id)}
                        disabled={isActive}
                      >
                        {isActive ? 'Active' : 'Set active'}
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}




