'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { ApiError } from '@/orchestration/http';
import {
  createOrganization,
  createProject,
  fetchOrganizations,
  inviteToOrganization,
  inviteToProject,
  type Organization,
} from '@/orchestration/organizations';

interface ProjectInviteInputs {
  [projectId: string]: string;
}

interface ProjectInviteState {
  [organizationId: string]: ProjectInviteInputs;
}

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
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [newOrganizationName, setNewOrganizationName] = useState('');
  const [newProjectNames, setNewProjectNames] = useState<Record<string, string>>({});
  const [organizationInvites, setOrganizationInvites] = useState<Record<string, string>>({});
  const [projectInvites, setProjectInvites] = useState<ProjectInviteState>({});
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackTone, setFeedbackTone] = useState<'positive' | 'negative'>('positive');

  const showFeedback = useCallback((message: string, tone: 'positive' | 'negative' = 'positive') => {
    setFeedback(message);
    setFeedbackTone(tone);
    const timeout = window.setTimeout(() => setFeedback(null), 5000);
    return () => window.clearTimeout(timeout);
  }, []);

  const refreshOrganizations = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchOrganizations();
      setOrganizations(data);
    } catch (error) {
      showFeedback(resolveErrorMessage(error), 'negative');
    } finally {
      setLoading(false);
    }
  }, [showFeedback]);

  useEffect(() => {
    void refreshOrganizations();
  }, [refreshOrganizations]);

  const hasOrganizations = useMemo(() => organizations.length > 0, [organizations]);

  async function handleCreateOrganization(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!newOrganizationName.trim()) {
      showFeedback('Please provide a name for your organization.', 'negative');
      return;
    }
    try {
      await createOrganization({ name: newOrganizationName.trim() });
      setNewOrganizationName('');
      showFeedback('Organization created.', 'positive');
      await refreshOrganizations();
    } catch (error) {
      showFeedback(resolveErrorMessage(error), 'negative');
    }
  }

  async function handleCreateProject(
    event: React.FormEvent<HTMLFormElement>,
    organization: Organization,
  ): Promise<void> {
    event.preventDefault();
    const projectName = newProjectNames[organization.id]?.trim() ?? '';
    if (!projectName) {
      showFeedback('Please provide a name for the project.', 'negative');
      return;
    }
    try {
      await createProject(organization.id, { name: projectName });
      setNewProjectNames((current) => ({ ...current, [organization.id]: '' }));
      showFeedback(`Project "${projectName}" created.`, 'positive');
      await refreshOrganizations();
    } catch (error) {
      showFeedback(resolveErrorMessage(error), 'negative');
    }
  }

  async function handleInviteToOrganization(
    event: React.FormEvent<HTMLFormElement>,
    organization: Organization,
  ): Promise<void> {
    event.preventDefault();
    const username = organizationInvites[organization.id]?.trim() ?? '';
    if (!username) {
      showFeedback('Enter a username to send an invite.', 'negative');
      return;
    }
    try {
      await inviteToOrganization(organization.id, { username });
      setOrganizationInvites((current) => ({ ...current, [organization.id]: '' }));
      showFeedback(`Invited ${username} to ${organization.name}.`, 'positive');
      await refreshOrganizations();
    } catch (error) {
      showFeedback(resolveErrorMessage(error), 'negative');
    }
  }

  async function handleInviteToProject(
    event: React.FormEvent<HTMLFormElement>,
    organizationId: string,
    projectId: string,
    projectName: string,
  ): Promise<void> {
    event.preventDefault();
    const username = projectInvites[organizationId]?.[projectId]?.trim() ?? '';
    if (!username) {
      showFeedback('Enter a username to invite to the project.', 'negative');
      return;
    }
    try {
      await inviteToProject(organizationId, projectId, { username });
      setProjectInvites((current) => ({
        ...current,
        [organizationId]: {
          ...(current[organizationId] ?? {}),
          [projectId]: '',
        },
      }));
      showFeedback(`Invited ${username} to ${projectName}.`, 'positive');
    } catch (error) {
      showFeedback(resolveErrorMessage(error), 'negative');
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-[color:var(--shell-bg)] text-[color:var(--text-primary)]">
      <header className="border-b border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-6 py-5 shadow-soft">
        <h1 className="text-xl font-semibold">Organizations & Projects</h1>
        <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
          Create shared workspaces, spin up projects, and bring collaborators into your teams.
        </p>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-8">
        {feedback && (
          <div
            role="status"
            className={`rounded-md border px-4 py-3 text-sm ${
              feedbackTone === 'positive'
                ? 'border-emerald-400 bg-emerald-50 text-emerald-800'
                : 'border-rose-400 bg-rose-50 text-rose-800'
            }`}
          >
            {feedback}
          </div>
        )}

        <section className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
          <h2 className="text-lg font-semibold">Create an organization</h2>
          <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
            Every organization can host many projects and invite multiple teammates.
          </p>
          <form onSubmit={handleCreateOrganization} className="mt-4 flex flex-wrap items-center gap-3">
            <label className="sr-only" htmlFor="new-organization-name">
              Organization name
            </label>
            <input
              id="new-organization-name"
              name="organizationName"
              value={newOrganizationName}
              onChange={(event) => setNewOrganizationName(event.target.value)}
              className="min-w-[240px] flex-1 rounded-md border border-[color:var(--border-strong)] bg-[color:var(--panel-alt)] px-3 py-2 text-sm focus:border-[color:var(--border-strong-hover)] focus:outline-none"
              placeholder="Acme Labs"
              autoComplete="off"
            />
            <button
              type="submit"
              className="rounded-md bg-[color:var(--text-primary)] px-4 py-2 text-sm font-semibold text-[color:var(--shell-bg)] transition hover:opacity-90"
            >
              Create organization
            </button>
          </form>
        </section>

        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Your organizations</h2>
            <p className="text-sm text-[color:var(--text-secondary)]">
              {loading
                ? 'Loading organizations...'
                : hasOrganizations
                  ? 'Manage the projects inside each organization and invite teammates as needed.'
                  : 'You are not part of any additional organizations yet.'}
            </p>
          </div>

          {!loading && hasOrganizations && (
            <div className="space-y-6">
              {organizations.map((organization) => (
                <article
                  key={organization.id}
                  className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold">{organization.name}</h3>
                      <p className="text-xs text-[color:var(--text-secondary)]">
                        {organization.memberCount} member{organization.memberCount === 1 ? '' : 's'}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <form
                      onSubmit={(event) => handleInviteToOrganization(event, organization)}
                      className="rounded-lg border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
                    >
                      <h4 className="text-sm font-medium">Invite to organization</h4>
                      <p className="mt-1 text-xs text-[color:var(--text-secondary)]">
                        Add an existing LangBridge user by their username.
                      </p>
                      <label className="sr-only" htmlFor={`invite-org-${organization.id}`}>
                        Username to invite
                      </label>
                      <div className="mt-3 flex gap-2">
                        <input
                          id={`invite-org-${organization.id}`}
                          value={organizationInvites[organization.id] ?? ''}
                          onChange={(event) =>
                            setOrganizationInvites((current) => ({
                              ...current,
                              [organization.id]: event.target.value,
                            }))
                          }
                          placeholder="username"
                          className="flex-1 rounded-md border border-[color:var(--border-strong)] bg-[color:var(--panel-bg)] px-3 py-2 text-sm focus:border-[color:var(--border-strong-hover)] focus:outline-none"
                        />
                        <button
                          type="submit"
                          className="rounded-md bg-[color:var(--text-primary)] px-3 py-2 text-xs font-semibold text-[color:var(--shell-bg)] transition hover:opacity-90"
                        >
                          Invite
                        </button>
                      </div>
                    </form>

                    <form
                      onSubmit={(event) => handleCreateProject(event, organization)}
                      className="rounded-lg border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
                    >
                      <h4 className="text-sm font-medium">New project</h4>
                      <p className="mt-1 text-xs text-[color:var(--text-secondary)]">
                        Projects keep data sources and agents scoped within the organization.
                      </p>
                      <label className="sr-only" htmlFor={`new-project-${organization.id}`}>
                        Project name
                      </label>
                      <div className="mt-3 flex gap-2">
                        <input
                          id={`new-project-${organization.id}`}
                          value={newProjectNames[organization.id] ?? ''}
                          onChange={(event) =>
                            setNewProjectNames((current) => ({
                              ...current,
                              [organization.id]: event.target.value,
                            }))
                          }
                          placeholder="Project name"
                          className="flex-1 rounded-md border border-[color:var(--border-strong)] bg-[color:var(--panel-bg)] px-3 py-2 text-sm focus:border-[color:var(--border-strong-hover)] focus:outline-none"
                        />
                        <button
                          type="submit"
                          className="rounded-md bg-[color:var(--text-primary)] px-3 py-2 text-xs font-semibold text-[color:var(--shell-bg)] transition hover:opacity-90"
                        >
                          Create
                        </button>
                      </div>
                    </form>
                  </div>

                  <div className="mt-6">
                    <h4 className="text-sm font-semibold">Projects</h4>
                    {organization.projects.length === 0 ? (
                      <p className="mt-2 text-sm text-[color:var(--text-secondary)]">
                        No projects yet. Create one to start organizing connectors and agents.
                      </p>
                    ) : (
                      <ul className="mt-3 space-y-3">
                        {organization.projects.map((project) => (
                          <li
                            key={project.id}
                            className="rounded-lg border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <h5 className="text-sm font-medium">{project.name}</h5>
                                <p className="text-xs text-[color:var(--text-secondary)]">
                                  Project ID: {project.id}
                                </p>
                              </div>
                            </div>
                            <form
                              onSubmit={(event) =>
                                handleInviteToProject(event, organization.id, project.id, project.name)
                              }
                              className="mt-3 flex gap-2"
                            >
                              <label className="sr-only" htmlFor={`invite-${organization.id}-${project.id}`}>
                                Username to invite to {project.name}
                              </label>
                              <input
                                id={`invite-${organization.id}-${project.id}`}
                                value={projectInvites[organization.id]?.[project.id] ?? ''}
                                onChange={(event) =>
                                  setProjectInvites((current) => ({
                                    ...current,
                                    [organization.id]: {
                                      ...(current[organization.id] ?? {}),
                                      [project.id]: event.target.value,
                                    },
                                  }))
                                }
                                placeholder="username"
                                className="flex-1 rounded-md border border-[color:var(--border-strong)] bg-[color:var(--panel-bg)] px-3 py-2 text-sm focus:border-[color:var(--border-strong-hover)] focus:outline-none"
                              />
                              <button
                                type="submit"
                                className="rounded-md bg-[color:var(--text-primary)] px-3 py-2 text-xs font-semibold text-[color:var(--shell-bg)] transition hover:opacity-90"
                              >
                                Invite
                              </button>
                            </form>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}








