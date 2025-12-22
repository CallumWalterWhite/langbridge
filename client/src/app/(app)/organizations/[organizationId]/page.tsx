'use client';

import Link from 'next/link';
import { JSX, useMemo } from 'react';
import { ArrowLeft, Folder, RefreshCw, Settings2, Users } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useWorkspaceScope } from '@/context/workspaceScope';

type OrganizationDetailPageProps = {
  params: { organizationId: string };
};

export default function OrganizationDetailPage({ params }: OrganizationDetailPageProps): JSX.Element {
  const {
    organizations,
    loading,
    error,
    selectedOrganizationId,
    selectedProjectId,
    setSelectedOrganizationId,
    setSelectedProjectId,
    refreshOrganizations,
  } = useWorkspaceScope();

  const organization = useMemo(
    () => organizations.find((item) => item.id === params.organizationId) ?? null,
    [organizations, params.organizationId],
  );

  const projects = useMemo(
    () => (organization?.projects ?? []).slice().sort((a, b) => a.name.localeCompare(b.name)),
    [organization],
  );

  const activeProject = useMemo(
    () => organization?.projects.find((project) => project.id === selectedProjectId) ?? null,
    [organization, selectedProjectId],
  );

  const showLoadingState = loading && organizations.length === 0;
  const isActive = organization?.id === selectedOrganizationId;

  const handleActivateOrganization = () => {
    if (organization) {
      setSelectedOrganizationId(organization.id);
    }
  };

  const handleActivateProject = (projectId: string) => {
    if (!organization) {
      return;
    }
    setSelectedOrganizationId(organization.id);
    setSelectedProjectId(projectId);
  };

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <Link
              href="/organizations"
              className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]"
            >
              Organizations
            </Link>
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
                  {showLoadingState ? 'Loading organization' : organization?.name ?? 'Organization not found'}
                </h1>
                {organization && isActive ? <Badge variant="secondary">Active</Badge> : null}
              </div>
              <p className="text-sm md:text-base">
                {organization
                  ? 'Review membership, scope, and projects associated with this workspace.'
                  : 'Select an organization from the list to view its details.'}
              </p>
              {organization ? (
                <p className="text-xs text-[color:var(--text-muted)]">
                  {isActive
                    ? activeProject
                      ? `Active project: ${activeProject.name}`
                      : 'Active for all projects.'
                    : 'Not in your active workspace scope.'}
                </p>
              ) : null}
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-end">
            <Button asChild variant="outline" size="sm" className="gap-2">
              <Link href="/organizations">
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                Back to list
              </Link>
            </Button>
            {organization ? (
              <>
                <Button
                  onClick={handleActivateOrganization}
                  size="sm"
                  variant={isActive ? 'secondary' : 'default'}
                  className="gap-2"
                  disabled={isActive}
                >
                  <Users className="h-4 w-4" aria-hidden="true" />
                  {isActive ? 'Active workspace' : 'Set as active'}
                </Button>
                <Button asChild variant="outline" size="sm" className="gap-2">
                  <Link href={`/organizations/${organization.id}/settings`}>
                    <Settings2 className="h-4 w-4" aria-hidden="true" />
                    Organization settings
                  </Link>
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </header>

      {showLoadingState ? (
        <>
          <section className="surface-panel rounded-3xl p-6 shadow-soft">
            <div className="flex items-center justify-between gap-3">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-8 w-24" />
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              {Array.from({ length: 2 }).map((_, index) => (
                <div
                  key={index}
                  className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                >
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="mt-3 h-6 w-16" />
                </div>
              ))}
            </div>
          </section>
          <section className="surface-panel rounded-3xl p-6 shadow-soft">
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index}
                  className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
                >
                  <Skeleton className="h-4 w-32" />
                </div>
              ))}
            </div>
          </section>
        </>
      ) : !organization ? (
        <section className="surface-panel flex flex-col items-center justify-center gap-4 rounded-3xl p-6 text-center text-[color:var(--text-muted)] shadow-soft">
          <p className="text-sm">
            {error ? 'We could not load this organization right now.' : 'That organization is not available.'}
          </p>
          <Button onClick={() => refreshOrganizations()} variant="outline" size="sm">
            Try again
          </Button>
        </section>
      ) : (
        <>
          <section className="surface-panel rounded-3xl p-6 shadow-soft">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Overview</h2>
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

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                  Members
                </p>
                <p className="mt-2 text-2xl font-semibold text-[color:var(--text-primary)]">
                  {organization.memberCount}
                </p>
                <p className="text-xs text-[color:var(--text-muted)]">Active collaborators</p>
              </div>
              <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                  Projects
                </p>
                <p className="mt-2 text-2xl font-semibold text-[color:var(--text-primary)]">
                  {organization.projects.length}
                </p>
                <p className="text-xs text-[color:var(--text-muted)]">Workspace scopes</p>
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">
                Organization ID
              </p>
              <p className="mt-2 break-all font-mono text-xs text-[color:var(--text-primary)]">
                {organization.id}
              </p>
            </div>
          </section>

          <section className="surface-panel flex flex-1 flex-col rounded-3xl p-6 shadow-soft">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-[color:var(--text-primary)]">Projects</h2>
                <p className="text-xs text-[color:var(--text-muted)]">
                  {organization.projects.length} project{organization.projects.length === 1 ? '' : 's'} in this
                  organization.
                </p>
              </div>
              <Button asChild variant="outline" size="sm" className="gap-2">
                <Link href={`/organizations/${organization.id}/settings`}>
                  <Settings2 className="h-4 w-4" aria-hidden="true" />
                  Create project
                </Link>
              </Button>
            </div>

            <div className="mt-6 flex-1">
              {projects.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[color:var(--text-muted)]">
                  <div className="inline-flex items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-3 py-1 text-xs font-medium">
                    No projects yet
                  </div>
                  <div className="space-y-2">
                    <p className="text-base font-semibold text-[color:var(--text-primary)]">No projects found</p>
                    <p className="text-sm">Create a project to scope connectors, agents, and models.</p>
                  </div>
                </div>
              ) : (
                <ul className="space-y-3">
                  {projects.map((project) => {
                    const projectActive = project.id === selectedProjectId && isActive;
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
                              {projectActive ? <Badge variant="secondary">Active</Badge> : null}
                            </div>
                            <p className="text-xs text-[color:var(--text-muted)]">Project ID: {project.id}</p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleActivateProject(project.id)}
                          disabled={projectActive}
                        >
                          {projectActive ? 'Active' : 'Set active'}
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
