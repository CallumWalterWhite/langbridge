'use client';

import { JSX, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Bot, BrainCircuit, Sparkles } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { ApiError } from '@/orchestration/http';
import {
  createLLMConnection,
  type CreateLLMConnectionPayload,
  type LLMConnection,
  type LLMProvider,
} from '@/orchestration/agents';
import { useWorkspaceScope } from '@/context/workspaceScope';

type FeedbackTone = 'positive' | 'negative';

interface FeedbackState {
  message: string;
  tone: FeedbackTone;
}

interface LLMProviderCard {
  id: LLMProvider;
  label: string;
  description: string;
  icon: LucideIcon;
  badge?: string;
}

interface FormState {
  name: string;
  model: string;
  apiKey: string;
  description: string;
  configuration: string;
  organizationId: string;
  projectId: string;
}

interface ProjectOption {
  id: string;
  name: string;
  organizationName: string;
}

const PROVIDER_CARDS: LLMProviderCard[] = [
  {
    id: 'openai',
    label: 'OpenAI',
    description: 'Ship GPT-4o mini, GPT-4o, and function calling agents with guardrails by default.',
    icon: Sparkles,
  },
  {
    id: 'anthropic',
    label: 'Anthropic',
    description: 'Pair Claude 3 family models with your workflows for reasoning-heavy playbooks.',
    icon: Bot,
  },
  {
    id: 'azure',
    label: 'Azure OpenAI',
    description: 'Point to enterprise deployments of GPT models and inherit Azure policy controls.',
    icon: BrainCircuit,
    badge: 'Enterprise',
  },
];

function resolveErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

export default function AgentsPage(): JSX.Element {
  const [selectedProvider, setSelectedProvider] = useState<LLMProvider | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [createdConnection, setCreatedConnection] = useState<LLMConnection | null>(null);
  const [formState, setFormState] = useState<FormState>({
    name: '',
    model: '',
    apiKey: '',
    description: '',
    configuration: '',
    organizationId: '',
    projectId: '',
  });
  const feedbackTimeout = useRef<number | undefined>(undefined);

  const organizationId = formState.organizationId;
  const projectId = formState.projectId;

  const { organizations, loading: organizationsLoading, selectedOrganizationId: activeOrganizationId, selectedProjectId: activeProjectId } =
    useWorkspaceScope();

  const projectOptions = useMemo<ProjectOption[]>(() => {
    if (organizationId) {
      const organization = organizations.find((item) => item.id === organizationId);
      return (organization?.projects ?? []).map((project) => ({
        id: project.id,
        name: project.name,
        organizationName: organization?.name ?? 'Unknown organization',
      }));
    }

    return organizations.flatMap((organization) =>
      (organization.projects ?? []).map((project) => ({
        id: project.id,
        name: project.name,
        organizationName: organization.name,
      })),
    );
  }, [organizationId, organizations]);

  const showFeedback = useCallback((message: string, tone: FeedbackTone = 'positive') => {
    setFeedback({ message, tone });
    if (feedbackTimeout.current) {
      window.clearTimeout(feedbackTimeout.current);
    }
    feedbackTimeout.current = window.setTimeout(() => setFeedback(null), 5000);
  }, []);

  useEffect(() => {
    return () => {
      if (feedbackTimeout.current) {
        window.clearTimeout(feedbackTimeout.current);
      }
    };
  }, []);

  useEffect(() => {
    setFormState((current) => {
      const nextOrganization = activeOrganizationId ?? '';
      const nextProject = activeProjectId ?? '';
      if (current.organizationId === nextOrganization && current.projectId === nextProject) {
        return current;
      }
      return {
        ...current,
        organizationId: nextOrganization,
        projectId: nextProject,
      };
    });
  }, [activeOrganizationId, activeProjectId]);

  useEffect(() => {
    if (!organizationId || !projectId) {
      return;
    }

    const organization = organizations.find((item) => item.id === organizationId);
    const belongsToOrganization = organization?.projects?.some((project) => project.id === projectId);

    if (!belongsToOrganization) {
      setFormState((current) => ({ ...current, projectId: '' }));
    }
  }, [organizationId, organizations, projectId]);

  const formIsDisabled = submitting || organizationsLoading;

  function handleProviderSelect(provider: LLMProvider) {
    setSelectedProvider(provider);
  }

  function handleFieldChange<K extends keyof FormState>(field: K, value: FormState[K]) {
    setFormState((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function validateForm(): string | null {
    if (!selectedProvider) {
      return 'Choose a provider to get started.';
    }

    if (!formState.name.trim()) {
      return 'Add a name so your teammates can identify the connection.';
    }

    if (!formState.model.trim()) {
      return 'Specify the model the agent should call.';
    }

    if (!formState.apiKey.trim()) {
      return 'Provide an API key so we can authenticate with the provider.';
    }

    if (!formState.organizationId.trim() && !formState.projectId.trim()) {
      return 'Add an organization or project so we know where to attach this connection.';
    }

    return null;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errorMessage = validateForm();

    if (errorMessage) {
      showFeedback(errorMessage, 'negative');
      return;
    }

    let parsedConfiguration: Record<string, unknown> | undefined;
    if (formState.configuration.trim()) {
      try {
        parsedConfiguration = JSON.parse(formState.configuration);
      } catch {
        showFeedback('Configuration must be valid JSON.', 'negative');
        return;
      }
    }

    const payload: CreateLLMConnectionPayload = {
      name: formState.name.trim(),
      provider: selectedProvider!,
      model: formState.model.trim(),
      apiKey: formState.apiKey.trim(),
      description: formState.description.trim() || undefined,
      configuration: parsedConfiguration,
    };

    if (formState.organizationId.trim()) {
      payload.organizationId = formState.organizationId.trim();
    }

    if (formState.projectId.trim()) {
      payload.projectId = formState.projectId.trim();
    }

    try {
      setSubmitting(true);
      const connection = await createLLMConnection(payload);
      setCreatedConnection(connection);
      showFeedback(`Connection "${connection.name}" created successfully.`, 'positive');
    } catch (error) {
      showFeedback(resolveErrorMessage(error), 'negative');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8 text-[color:var(--text-secondary)]">
      {feedback ? (
        <div
          role="alert"
          className={cn(
            'rounded-lg border px-4 py-3 text-sm shadow-soft',
            feedback.tone === 'positive'
              ? 'border-emerald-400/60 bg-emerald-500/10 text-emerald-800'
              : 'border-rose-400/60 bg-rose-500/10 text-rose-800',
          )}
        >
          {feedback.message}
        </div>
      ) : null}

      <section className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-[color:var(--text-primary)]">Choose a provider</h2>
            <p className="text-sm">
              We will pre-wire the connection so you can plug it into agents and orchestrations later.
            </p>
          </div>
          <Badge variant="secondary" className="text-xs uppercase tracking-wide text-[color:var(--text-secondary)]">
            Agent builder soon
          </Badge>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PROVIDER_CARDS.map((card) => (
            <ProviderCard
              key={card.id}
              card={card}
              isSelected={selectedProvider === card.id}
              onSelect={handleProviderSelect}
            />
          ))}
        </div>
      </section>

      <section className="space-y-6">
        <header className="space-y-2">
          <h2 className="text-xl font-semibold text-[color:var(--text-primary)]">Connection details</h2>
          <p className="text-sm">
            Fill in the provider credentials and scope. We test the connection before saving it.
          </p>
        </header>

        <form
          className="space-y-8 rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft"
          onSubmit={(event) => void handleSubmit(event)}
        >
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-3">
              <Label htmlFor="connection-name" className="text-[color:var(--text-secondary)]">
                Connection name
              </Label>
              <Input
                id="connection-name"
                value={formState.name}
                disabled={formIsDisabled}
                placeholder="Ops copilot connection"
                onChange={(event) => handleFieldChange('name', event.target.value)}
              />
            </div>

            <div className="space-y-3">
              <Label htmlFor="connection-model" className="text-[color:var(--text-secondary)]">
                Default model
              </Label>
              <Input
                id="connection-model"
                value={formState.model}
                disabled={formIsDisabled}
                placeholder={
                  selectedProvider === 'openai'
                    ? 'gpt-4o-mini'
                    : selectedProvider === 'anthropic'
                      ? 'claude-3-haiku'
                      : 'gpt-4o'
                }
                onChange={(event) => handleFieldChange('model', event.target.value)}
              />
            </div>

            <div className="space-y-3">
              <Label htmlFor="connection-api-key" className="text-[color:var(--text-secondary)]">
                API key
              </Label>
              <Input
                id="connection-api-key"
                type="password"
                value={formState.apiKey}
                disabled={formIsDisabled}
                placeholder="sk-..."
                onChange={(event) => handleFieldChange('apiKey', event.target.value)}
              />
            </div>

            <div className="space-y-3">
              <Label htmlFor="connection-description" className="text-[color:var(--text-secondary)]">
                Description
              </Label>
              <Textarea
                id="connection-description"
                value={formState.description}
                disabled={formIsDisabled}
                placeholder="Describe the use case or neighboring teams."
                onChange={(event) => handleFieldChange('description', event.target.value)}
              />
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <h3 className="text-base font-semibold text-[color:var(--text-primary)]">Connection scope</h3>
              <p className="text-sm">
                Add the organization or project that should own this connection. Provide at least one ID.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="organization-id" className="text-[color:var(--text-secondary)]">
                  Organization
                </Label>
                <Select
                  id="organization-id"
                  value={organizationId}
                  disabled={organizationsLoading || organizations.length === 0}
                  placeholder={organizationsLoading ? 'Loading organizations...' : 'Select an organization'}
                  onChange={(event) => handleFieldChange('organizationId', event.target.value)}
                >
                  {organizations.map((organization) => (
                    <option key={organization.id} value={organization.id}>
                      {organization.name}
                    </option>
                  ))}
                </Select>
                {organizations.length === 0 && !organizationsLoading ? (
                  <p className="text-xs text-[color:var(--text-muted)]">
                    You do not have any organizations yet. Create one to continue.
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="project-id" className="text-[color:var(--text-secondary)]">
                  Project
                </Label>
                <Select
                  id="project-id"
                  value={projectId}
                  disabled={projectOptions.length === 0}
                  placeholder={
                    organizationId
                      ? projectOptions.length > 0
                        ? 'Select a project'
                        : 'No projects found for this organization'
                      : 'Select a project'
                  }
                  onChange={(event) => handleFieldChange('projectId', event.target.value)}
                >
                  {projectOptions.map((project) => (
                    <option key={project.id} value={project.id}>
                      {organizationId ? project.name : `${project.organizationName} - ${project.name}`}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <Label htmlFor="connection-configuration" className="text-[color:var(--text-secondary)]">
              Provider configuration (JSON)
            </Label>
            <Textarea
              id="connection-configuration"
              value={formState.configuration}
              disabled={formIsDisabled}
              className="min-h-[160px] font-mono text-sm"
              placeholder='{"temperature": 0.2, "timeout": 30}'
              onChange={(event) => handleFieldChange('configuration', event.target.value)}
            />
            <p className="text-xs text-[color:var(--text-muted)]">
              Include deployment IDs, base URLs, or model-specific overrides. Leave blank to use provider defaults.
            </p>
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-[color:var(--panel-border)] pt-4 text-xs">
            <div className="text-[color:var(--text-muted)]">
              We validate the connection before adding it to your workspace.
            </div>
            <Button type="submit" disabled={formIsDisabled} isLoading={submitting} loadingText="Creating...">
              Create connection
            </Button>
          </div>
        </form>
      </section>

      {createdConnection ? (
        <section className="rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 shadow-soft">
          <h3 className="text-base font-semibold text-[color:var(--text-primary)]">Connection ready to use</h3>
          <p className="mt-1 text-sm">
            We saved {createdConnection.name}. Keep these identifiers handy while we build the agent editor.
          </p>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="font-medium text-[color:var(--text-primary)]">Connection ID</dt>
              <dd className="mt-1 font-mono text-xs">{createdConnection.id ?? 'Not returned'}</dd>
            </div>
            <div>
              <dt className="font-medium text-[color:var(--text-primary)]">Provider</dt>
              <dd className="mt-1 font-mono text-xs uppercase">{createdConnection.provider}</dd>
            </div>
            <div>
              <dt className="font-medium text-[color:var(--text-primary)]">Organization</dt>
              <dd className="mt-1 font-mono text-xs">{createdConnection.organizationId ?? 'Not provided'}</dd>
            </div>
            <div>
              <dt className="font-medium text-[color:var(--text-primary)]">Project</dt>
              <dd className="mt-1 font-mono text-xs">{createdConnection.projectId ?? 'Not provided'}</dd>
            </div>
          </dl>
        </section>
      ) : null}
    </div>
  );
}

function ProviderCard({
  card,
  isSelected,
  onSelect,
}: {
  card: LLMProviderCard;
  isSelected: boolean;
  onSelect: (provider: LLMProvider) => void;
}): JSX.Element {
  const IconComponent = card.icon ?? Sparkles;
  return (
    <button
      type="button"
      onClick={() => onSelect(card.id)}
      aria-pressed={isSelected}
      className={cn(
        'group flex h-full flex-col justify-between gap-4 rounded-xl border p-4 text-left transition hover:-translate-y-1 hover:border-[color:var(--accent)] hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]',
        isSelected
          ? 'border-[color:var(--accent)] bg-[color:var(--panel-alt)] shadow-lg'
          : 'border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] shadow-soft',
      )}
    >
      <div className="flex items-start gap-4">
        <span
          className={cn(
            'flex h-12 w-12 items-center justify-center rounded-full bg-[color:var(--panel-alt)] text-[color:var(--accent)] transition group-hover:scale-105',
            isSelected ? 'bg-[color:var(--accent-soft)] text-[color:var(--accent-strong)]' : '',
          )}
        >
          <IconComponent className="h-6 w-6" aria-hidden />
        </span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-[color:var(--text-primary)]">{card.label}</h3>
            {card.badge ? (
              <Badge variant="secondary" className="text-xs uppercase tracking-wide">
                {card.badge}
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 line-clamp-3 text-xs text-[color:var(--text-secondary)]">{card.description}</p>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs text-[color:var(--text-secondary)]">
        <span className="uppercase tracking-wide">Select</span>
          <span aria-hidden>{isSelected ? '>>' : '>'}</span>
      </div>
    </button>
  );
}



