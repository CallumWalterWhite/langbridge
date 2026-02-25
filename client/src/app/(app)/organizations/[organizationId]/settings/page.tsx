'use client';

import Link from 'next/link';
import { JSX, useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/orchestration/http';
import {
  createProject,
  deleteOrganizationEnvironmentSetting,
  fetchOrganizationEnvironmentKeys,
  fetchOrganizationEnvironmentSettings,
  inviteToOrganization,
  inviteToProject,
  setOrganizationEnvironmentSetting,
  type OrganizationEnvironmentSetting,
} from '@/orchestration/organizations';
import { useWorkspaceScope } from '@/context/workspaceScope';

type OrganizationSettingsPageProps = {
  params: { organizationId: string };
};

const environmentKeysQueryKey = ['organization-env-keys'] as const;
const environmentSettingsQueryKey = (organizationId: string | null | undefined) =>
  ['organization-env-settings', organizationId] as const;

const ENVIRONMENT_SETTING_META: Record<
  string,
  {
    label: string;
    description: string;
    placeholder?: string;
    inputType?: 'text' | 'email';
    multiline?: boolean;
    options?: string[];
  }
> = {
  staging_db_connection: {
    label: 'Staging DB connection',
    description: 'Connection string used by staging data workflows.',
    placeholder: 'postgres://user:password@host:5432/dbname',
    multiline: true,
  },
  support_email: {
    label: 'Support email',
    description: 'Default reply-to address for customer support.',
    placeholder: 'support@company.com',
    inputType: 'email',
  },
  feature_flag_new_dashboard: {
    label: 'New dashboard flag',
    description: 'Toggle the new dashboard experience for this organization.',
    options: ['true', 'false'],
  },
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

function formatSettingLabel(settingKey: string): string {
  return settingKey
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}

export default function OrganizationSettingsPage({ params }: OrganizationSettingsPageProps): JSX.Element {
  const { organizations, loading, refreshOrganizations: reloadOrganizations } = useWorkspaceScope();
  const queryClient = useQueryClient();

  const organization = useMemo(
    () => organizations.find((item) => item.id === params.organizationId) ?? null,
    [organizations, params.organizationId],
  );

  const projects = useMemo(() => organization?.projects ?? [], [organization]);

  const [newProjectName, setNewProjectName] = useState('');
  const [organizationInvite, setOrganizationInvite] = useState('');
  const [projectInvites, setProjectInvites] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackTone, setFeedbackTone] = useState<'positive' | 'negative'>('positive');

  const showFeedback = useCallback((message: string, tone: 'positive' | 'negative' = 'positive') => {
    setFeedback(message);
    setFeedbackTone(tone);
    const timeout = window.setTimeout(() => setFeedback(null), 5000);
    return () => window.clearTimeout(timeout);
  }, []);

  const environmentKeysQuery = useQuery<string[]>({
    queryKey: environmentKeysQueryKey,
    queryFn: () => fetchOrganizationEnvironmentKeys(),
    refetchOnWindowFocus: false,
  });

  const environmentSettingsQuery = useQuery<OrganizationEnvironmentSetting[]>({
    queryKey: environmentSettingsQueryKey(params.organizationId),
    queryFn: () => fetchOrganizationEnvironmentSettings(params.organizationId),
    enabled: Boolean(params.organizationId),
    refetchOnWindowFocus: false,
  });

  const [environmentDraft, setEnvironmentDraft] = useState<Record<string, string>>({});
  const [environmentDraftOrgId, setEnvironmentDraftOrgId] = useState<string>('');
  const [pendingEnvironmentActions, setPendingEnvironmentActions] = useState<
    Record<string, 'save' | 'clear'>
  >({});

  const availableEnvironmentKeys = useMemo(
    () => environmentKeysQuery.data ?? [],
    [environmentKeysQuery.data],
  );

  const environmentSettingsByKey = useMemo(() => {
    return new Map(
      (environmentSettingsQuery.data ?? []).map((setting) => [setting.settingKey, setting.settingValue]),
    );
  }, [environmentSettingsQuery.data]);

  const hasEnvironmentDraft = useMemo(
    () => Object.keys(environmentDraft).length > 0,
    [environmentDraft],
  );

  const hydrateEnvironmentDraft = useCallback(
    (keys: string[], settings: OrganizationEnvironmentSetting[]) => {
      const next: Record<string, string> = {};
      const existing = new Map(settings.map((setting) => [setting.settingKey, setting.settingValue]));
      keys.forEach((key) => {
        next[key] = existing.get(key) ?? '';
      });
      return next;
    },
    [],
  );

  useEffect(() => {
    if (!params.organizationId) {
      setEnvironmentDraft({});
      setEnvironmentDraftOrgId('');
      return;
    }

    const keysReady = environmentKeysQuery.isFetched;
    const settingsReady = environmentSettingsQuery.isFetched;
    if (!keysReady || !settingsReady) {
      return;
    }

    if (environmentDraftOrgId === params.organizationId && hasEnvironmentDraft) {
      return;
    }

    const nextDraft = hydrateEnvironmentDraft(
      availableEnvironmentKeys,
      environmentSettingsQuery.data ?? [],
    );
    setEnvironmentDraft(nextDraft);
    setEnvironmentDraftOrgId(params.organizationId);
  }, [
    params.organizationId,
    environmentKeysQuery.isFetched,
    environmentSettingsQuery.isFetched,
    environmentSettingsQuery.data,
    environmentDraftOrgId,
    hasEnvironmentDraft,
    availableEnvironmentKeys,
    hydrateEnvironmentDraft,
  ]);

  const saveEnvironmentSettingMutation = useMutation({
    mutationFn: async ({
      organizationId,
      settingKey,
      settingValue,
    }: {
      organizationId: string;
      settingKey: string;
      settingValue: string;
    }) => setOrganizationEnvironmentSetting(organizationId, settingKey, settingValue),
  });

  const clearEnvironmentSettingMutation = useMutation({
    mutationFn: async ({
      organizationId,
      settingKey,
    }: {
      organizationId: string;
      settingKey: string;
    }) => deleteOrganizationEnvironmentSetting(organizationId, settingKey),
  });

  const setEnvironmentAction = useCallback((settingKey: string, action?: 'save' | 'clear') => {
    setPendingEnvironmentActions((current) => {
      if (!action) {
        const next = { ...current };
        delete next[settingKey];
        return next;
      }
      return { ...current, [settingKey]: action };
    });
  }, []);

  const updateEnvironmentSettingCache = useCallback(
    (settingKey: string, settingValue: string) => {
      queryClient.setQueryData<OrganizationEnvironmentSetting[]>(
        environmentSettingsQueryKey(params.organizationId),
        (current) => {
          const next = current ? [...current] : [];
          const index = next.findIndex((setting) => setting.settingKey === settingKey);
          if (index >= 0) {
            next[index] = { settingKey, settingValue };
          } else {
            next.push({ settingKey, settingValue });
          }
          return next;
        },
      );
    },
    [queryClient, params.organizationId],
  );

  const removeEnvironmentSettingCache = useCallback(
    (settingKey: string) => {
      queryClient.setQueryData<OrganizationEnvironmentSetting[]>(
        environmentSettingsQueryKey(params.organizationId),
        (current) => {
          if (!current) {
            return [];
          }
          return current.filter((setting) => setting.settingKey !== settingKey);
        },
      );
    },
    [queryClient, params.organizationId],
  );

  const handleEnvironmentValueChange = useCallback((settingKey: string, value: string) => {
    setEnvironmentDraft((current) => ({ ...current, [settingKey]: value }));
  }, []);

  const handleRefreshEnvironmentSettings = useCallback(async () => {
    const keyResult = await environmentKeysQuery.refetch();
    const settingsResult = await environmentSettingsQuery.refetch();
    const nextDraft = hydrateEnvironmentDraft(
      keyResult.data ?? [],
      settingsResult.data ?? [],
    );
    setEnvironmentDraft(nextDraft);
    setEnvironmentDraftOrgId(params.organizationId);
  }, [
    environmentKeysQuery,
    environmentSettingsQuery,
    hydrateEnvironmentDraft,
    params.organizationId,
  ]);

  const handleSaveEnvironmentSetting = useCallback(
    async (settingKey: string) => {
      setEnvironmentAction(settingKey, 'save');
      try {
        const response = await saveEnvironmentSettingMutation.mutateAsync({
          organizationId: params.organizationId,
          settingKey,
          settingValue: environmentDraft[settingKey] ?? '',
        });
        updateEnvironmentSettingCache(settingKey, response.settingValue);
        setEnvironmentDraft((current) => ({ ...current, [settingKey]: response.settingValue }));
        const label = ENVIRONMENT_SETTING_META[settingKey]?.label ?? formatSettingLabel(settingKey);
        showFeedback(`${label} saved.`, 'positive');
      } catch (error) {
        showFeedback(resolveErrorMessage(error), 'negative');
      } finally {
        setEnvironmentAction(settingKey);
      }
    },
    [
      environmentDraft,
      params.organizationId,
      saveEnvironmentSettingMutation,
      setEnvironmentAction,
      updateEnvironmentSettingCache,
      showFeedback,
    ],
  );

  const handleClearEnvironmentSetting = useCallback(
    async (settingKey: string) => {
      setEnvironmentAction(settingKey, 'clear');
      try {
        await clearEnvironmentSettingMutation.mutateAsync({
          organizationId: params.organizationId,
          settingKey,
        });
        removeEnvironmentSettingCache(settingKey);
        setEnvironmentDraft((current) => ({ ...current, [settingKey]: '' }));
        const label = ENVIRONMENT_SETTING_META[settingKey]?.label ?? formatSettingLabel(settingKey);
        showFeedback(`${label} cleared.`, 'positive');
      } catch (error) {
        showFeedback(resolveErrorMessage(error), 'negative');
      } finally {
        setEnvironmentAction(settingKey);
      }
    },
    [
      params.organizationId,
      clearEnvironmentSettingMutation,
      removeEnvironmentSettingCache,
      setEnvironmentAction,
      showFeedback,
    ],
  );

  const environmentErrorMessage = useMemo(() => {
    if (environmentKeysQuery.error) {
      return resolveErrorMessage(environmentKeysQuery.error);
    }
    if (environmentSettingsQuery.error) {
      return resolveErrorMessage(environmentSettingsQuery.error);
    }
    return null;
  }, [environmentKeysQuery.error, environmentSettingsQuery.error]);

  const environmentLoading =
    environmentKeysQuery.isLoading || environmentSettingsQuery.isLoading;
  const environmentRefreshing =
    environmentKeysQuery.isFetching || environmentSettingsQuery.isFetching;

  const handleCreateProject = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!organization) {
        showFeedback('Select a valid organization before creating a project.', 'negative');
        return;
      }
      const projectName = newProjectName.trim();
      if (!projectName) {
        showFeedback('Please provide a name for the project.', 'negative');
        return;
      }
      try {
        await createProject(organization.id, { name: projectName });
        setNewProjectName('');
        showFeedback(`Project "${projectName}" created.`, 'positive');
        await reloadOrganizations();
      } catch (error) {
        showFeedback(resolveErrorMessage(error), 'negative');
      }
    },
    [newProjectName, organization, reloadOrganizations, showFeedback],
  );

  const handleInviteToOrganization = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!organization) {
        showFeedback('Select a valid organization before inviting teammates.', 'negative');
        return;
      }
      const username = organizationInvite.trim();
      if (!username) {
        showFeedback('Enter a username to send an invite.', 'negative');
        return;
      }
      try {
        await inviteToOrganization(organization.id, { username });
        setOrganizationInvite('');
        showFeedback(`Invited ${username} to ${organization.name}.`, 'positive');
        await reloadOrganizations();
      } catch (error) {
        showFeedback(resolveErrorMessage(error), 'negative');
      }
    },
    [organization, organizationInvite, reloadOrganizations, showFeedback],
  );

  const handleInviteToProject = useCallback(
    async (event: React.FormEvent<HTMLFormElement>, projectId: string, projectName: string) => {
      event.preventDefault();
      if (!organization) {
        showFeedback('Select a valid organization before inviting teammates.', 'negative');
        return;
      }
      const username = projectInvites[projectId]?.trim() ?? '';
      if (!username) {
        showFeedback('Enter a username to invite to the project.', 'negative');
        return;
      }
      try {
        await inviteToProject(organization.id, projectId, { username });
        setProjectInvites((current) => ({
          ...current,
          [projectId]: '',
        }));
        showFeedback(`Invited ${username} to ${projectName}.`, 'positive');
      } catch (error) {
        showFeedback(resolveErrorMessage(error), 'negative');
      }
    },
    [organization, projectInvites, showFeedback],
  );

  const organizationLoading = loading && organizations.length === 0;

  return (
    <div className="space-y-6 text-[color:var(--text-secondary)]">
      {feedback ? (
        <div
          role="status"
          className={`rounded-lg border px-4 py-3 text-sm shadow-soft ${
            feedbackTone === 'positive'
              ? 'border-emerald-400/60 bg-emerald-500/10 text-emerald-800'
              : 'border-rose-400/60 bg-rose-500/10 text-rose-800'
          }`}
        >
          {feedback}
        </div>
      ) : null}

      <header className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <Link
              href={`/organizations/${params.organizationId}`}
              className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]"
            >
              Organization
            </Link>
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold text-[color:var(--text-primary)] md:text-3xl">
                  {organization?.name ?? 'Organization settings'}
                </h1>
                {organization ? <Badge variant="secondary">Settings</Badge> : null}
              </div>
              <p className="text-sm md:text-base">
                Adjust organization-level environment values, projects, and invitations.
              </p>
            </div>
          </div>
          <Button asChild variant="outline" size="sm" className="gap-2">
            <Link href={`/organizations/${params.organizationId}`}>
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to overview
            </Link>
          </Button>
        </div>
      </header>

      {organizationLoading ? (
        <section className="surface-panel rounded-3xl p-6 shadow-soft">
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4"
              >
                <Skeleton className="h-4 w-40" />
                <Skeleton className="mt-3 h-10 w-full" />
              </div>
            ))}
          </div>
        </section>
      ) : !organization ? (
        <section className="surface-panel flex flex-col items-center justify-center gap-3 rounded-3xl p-6 text-center text-[color:var(--text-muted)] shadow-soft">
          <p className="text-sm">We couldn&apos;t find that organization.</p>
          <Button asChild variant="outline" size="sm">
            <Link href="/organizations">Return to organizations</Link>
          </Button>
        </section>
      ) : (
        <>
          <section className="surface-panel rounded-3xl p-6 shadow-soft">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-2">
                <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">
                  Environment settings
                </h2>
                <p className="text-sm">
                  Update organization-scoped connection strings, support defaults, and feature flags.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefreshEnvironmentSettings}
                disabled={environmentRefreshing || environmentLoading}
              >
                Refresh
              </Button>
            </div>

            <div className="mt-6">
              {environmentLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, index) => (
                    <div
                      key={index}
                      className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
                    >
                      <Skeleton className="h-4 w-40" />
                      <Skeleton className="mt-3 h-10 w-full" />
                    </div>
                  ))}
                </div>
              ) : environmentErrorMessage ? (
                <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-6 text-center text-[color:var(--text-muted)]">
                  <p className="text-sm">{environmentErrorMessage}</p>
                  <Button onClick={handleRefreshEnvironmentSettings} variant="outline" size="sm">
                    Try again
                  </Button>
                </div>
              ) : availableEnvironmentKeys.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-[color:var(--panel-border)] p-6 text-center text-[color:var(--text-muted)]">
                  <p className="text-sm">No environment setting keys are configured yet.</p>
                  <p className="text-xs">Ask an administrator to define organization settings.</p>
                </div>
              ) : (
                <ul className="space-y-4">
                  {availableEnvironmentKeys.map((settingKey) => {
                    const meta = ENVIRONMENT_SETTING_META[settingKey];
                    const label = meta?.label ?? formatSettingLabel(settingKey);
                    const description = meta?.description ?? 'Organization environment setting.';
                    const draftValue = environmentDraft[settingKey] ?? '';
                    const currentValue = environmentSettingsByKey.get(settingKey) ?? '';
                    const isDirty = draftValue !== currentValue;
                    const actionState = pendingEnvironmentActions[settingKey];
                    const isSaving = actionState === 'save';
                    const isClearing = actionState === 'clear';
                    const isPending = Boolean(actionState);
                    const isConfigured = Boolean(currentValue);

                    return (
                      <li
                        key={settingKey}
                        className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold text-[color:var(--text-primary)]">{label}</p>
                              {!isConfigured ? <Badge variant="secondary">Not set</Badge> : null}
                              {isDirty ? <Badge variant="warning">Unsaved</Badge> : null}
                            </div>
                            <p className="text-xs text-[color:var(--text-muted)]">{description}</p>
                            <p className="text-[10px] font-mono text-[color:var(--text-muted)]">{settingKey}</p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              isLoading={isSaving}
                              disabled={!isDirty || isPending}
                              onClick={() => handleSaveEnvironmentSetting(settingKey)}
                            >
                              Save
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              isLoading={isClearing}
                              disabled={!isConfigured || isPending}
                              onClick={() => handleClearEnvironmentSetting(settingKey)}
                            >
                              Clear
                            </Button>
                          </div>
                        </div>
                        <div className="mt-3">
                          {meta?.options ? (
                            <Select
                              value={draftValue}
                              onChange={(event) => handleEnvironmentValueChange(settingKey, event.target.value)}
                              disabled={isPending}
                            >
                              <option value="">Not set</option>
                              {meta.options.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </Select>
                          ) : meta?.multiline ? (
                            <Textarea
                              value={draftValue}
                              onChange={(event) => handleEnvironmentValueChange(settingKey, event.target.value)}
                              placeholder={meta.placeholder}
                              disabled={isPending}
                              className="min-h-[96px]"
                            />
                          ) : (
                            <Input
                              type={meta?.inputType ?? 'text'}
                              value={draftValue}
                              onChange={(event) => handleEnvironmentValueChange(settingKey, event.target.value)}
                              placeholder={meta?.placeholder}
                              disabled={isPending}
                            />
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>

          <section className="surface-panel rounded-3xl p-6 shadow-soft">
            <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">Organization access</h2>
            <p className="mt-1 text-sm">
              Invite teammates and create new projects inside {organization.name}.
            </p>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <form
                onSubmit={handleInviteToOrganization}
                className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
              >
                <h3 className="text-sm font-medium text-[color:var(--text-primary)]">Invite to organization</h3>
                <p className="mt-1 text-xs">
                  Add an existing LangBridge user by their username.
                </p>
                <label className="sr-only" htmlFor="invite-org-username">
                  Username to invite
                </label>
                <div className="mt-3 flex gap-2">
                  <Input
                    id="invite-org-username"
                    value={organizationInvite}
                    onChange={(event) => setOrganizationInvite(event.target.value)}
                    placeholder="username"
                  />
                  <Button type="submit" size="sm">
                    Invite
                  </Button>
                </div>
              </form>

              <form
                onSubmit={handleCreateProject}
                className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
              >
                <h3 className="text-sm font-medium text-[color:var(--text-primary)]">New project</h3>
                <p className="mt-1 text-xs">
                  Projects keep data sources and agents scoped within the organization.
                </p>
                <label className="sr-only" htmlFor="new-project-name">
                  Project name
                </label>
                <div className="mt-3 flex gap-2">
                  <Input
                    id="new-project-name"
                    value={newProjectName}
                    onChange={(event) => setNewProjectName(event.target.value)}
                    placeholder="Project name"
                  />
                  <Button type="submit" size="sm">
                    Create
                  </Button>
                </div>
              </form>
            </div>

            <div className="mt-6">
              <h3 className="text-sm font-semibold text-[color:var(--text-primary)]">Projects</h3>
              {projects.length === 0 ? (
                <p className="mt-2 text-sm">
                  No projects yet. Create one to start organizing connectors and agents.
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {projects.map((project) => (
                    <li
                      key={project.id}
                      className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <h4 className="text-sm font-medium text-[color:var(--text-primary)]">{project.name}</h4>
                          <p className="text-xs">Project ID: {project.id}</p>
                        </div>
                      </div>
                      <form
                        onSubmit={(event) => handleInviteToProject(event, project.id, project.name)}
                        className="mt-3 flex gap-2"
                      >
                        <label className="sr-only" htmlFor={`invite-${project.id}`}>
                          Username to invite to {project.name}
                        </label>
                        <Input
                          id={`invite-${project.id}`}
                          value={projectInvites[project.id] ?? ''}
                          onChange={(event) =>
                            setProjectInvites((current) => ({
                              ...current,
                              [project.id]: event.target.value,
                            }))
                          }
                          placeholder="username"
                        />
                        <Button type="submit" size="sm" variant="outline">
                          Invite
                        </Button>
                      </form>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
