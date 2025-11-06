'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Save } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { ApiError } from '@/orchestration/http';
import {
  fetchLLMConnection,
  updateLLMConnection,
  type LLMConnection,
  type UpdateLLMConnectionPayload,
} from '@/orchestration/agents';

interface LLMConnectionUpdateProps {
  connectionId: string;
}

const llmConnectionQueryKey = (connectionId: string) => ['llm-connection', connectionId] as const;

function resolveError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

export function LLMConnectionUpdate({ connectionId }: LLMConnectionUpdateProps): JSX.Element {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [name, setName] = useState('');
  const [model, setModel] = useState('');
  const [description, setDescription] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [configurationText, setConfigurationText] = useState('{}');
  const [isActive, setIsActive] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);

  const connectionQuery = useQuery({
    queryKey: llmConnectionQueryKey(connectionId),
    queryFn: () => fetchLLMConnection(connectionId),
  });

  const connection = connectionQuery.data;

  useEffect(() => {
    if (!connection) {
      return;
    }
    setName(connection.name);
    setModel(connection.model);
    setDescription(connection.description ?? '');
    setConfigurationText(JSON.stringify(connection.configuration ?? {}, null, 2));
    setIsActive(connection.isActive);
  }, [connection]);

  const updateMutation = useMutation({
    mutationFn: (payload: UpdateLLMConnectionPayload) => updateLLMConnection(connectionId, payload),
    onSuccess: (updatedConnection: LLMConnection) => {
      queryClient.setQueryData(llmConnectionQueryKey(connectionId), updatedConnection);
      queryClient.invalidateQueries({ queryKey: ['llm-connections'] });
      toast({
        title: 'Connection saved',
        description: `“${updatedConnection.name}” has been updated.`,
      });
      setApiKey('');
    },
    onError: (error: unknown) => {
      toast({
        title: 'Update failed',
        description: resolveError(error),
        variant: 'destructive',
      });
    },
  });

  const providerLabel = useMemo(() => {
    if (!connection) {
      return '';
    }
    switch (connection.provider) {
      case 'openai':
        return 'OpenAI';
      case 'anthropic':
        return 'Anthropic';
      case 'azure':
        return 'Azure OpenAI';
      default:
        return connection.provider;
    }
  }, [connection]);

  const handleSubmit: React.FormEventHandler<HTMLFormElement> = (event) => {
    event.preventDefault();
    setLocalError(null);

    if (!apiKey.trim()) {
      setLocalError('Provide an API key to save updates.');
      return;
    }

    let parsedConfiguration: Record<string, unknown> = {};
    const trimmedConfig = configurationText.trim();
    if (trimmedConfig) {
      try {
        parsedConfiguration = JSON.parse(trimmedConfig) as Record<string, unknown>;
      } catch {
        setLocalError('Configuration must be valid JSON.');
        return;
      }
    }

    const payload: UpdateLLMConnectionPayload = {
      name: name.trim(),
      apiKey: apiKey.trim(),
      model: model.trim(),
      description: description.trim() || undefined,
      configuration: parsedConfiguration,
      isActive,
      organizationId: connection?.organizationId ?? undefined,
      projectId: connection?.projectId ?? undefined,
    };

    updateMutation.mutate(payload);
  };

  if (connectionQuery.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="space-y-4">
          <Skeleton className="h-10 w-full max-w-md" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    );
  }

  if (connectionQuery.isError || !connection) {
    return (
      <div className="space-y-4 text-sm text-[color:var(--text-muted)]">
        <p>We couldn&apos;t load that LLM connection.</p>
        <Button variant="outline" size="sm" onClick={() => connectionQuery.refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-2 text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
          onClick={() => router.push('/agents')}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to connections
        </Button>
        <h1 className="text-xl font-semibold text-[color:var(--text-primary)]">{connection.name}</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="llm-connection-name">Name</Label>
            <Input
              id="llm-connection-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Production OpenAI"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="llm-connection-provider">Provider</Label>
            <Input id="llm-connection-provider" value={providerLabel} readOnly />
          </div>

          <div className="space-y-2">
            <Label htmlFor="llm-connection-model">Model</Label>
            <Input
              id="llm-connection-model"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="gpt-4o"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="llm-connection-api-key">API key</Label>
            <Input
              id="llm-connection-api-key"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="sk-..."
            />
            <p className="text-xs text-[color:var(--text-muted)]">Provide a fresh key when rotating credentials.</p>
          </div>

          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="llm-connection-description">Description</Label>
            <Textarea
              id="llm-connection-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Context about how this connection is used"
              rows={3}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="llm-connection-config">Configuration (JSON)</Label>
          <Textarea
            id="llm-connection-config"
            value={configurationText}
            onChange={(event) => setConfigurationText(event.target.value)}
            rows={10}
            className="font-mono text-xs"
          />
          <p className="text-xs text-[color:var(--text-muted)]">
            Extend the base configuration with provider-specific options, such as API endpoints or temperature.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <input
            id="llm-connection-active"
            type="checkbox"
            className="h-4 w-4 accent-[color:var(--border-strong)]"
            checked={isActive}
            onChange={(event) => setIsActive(event.target.checked)}
          />
          <Label htmlFor="llm-connection-active">Connection is active</Label>
        </div>

        {localError ? <p className="text-sm text-red-500">{localError}</p> : null}

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            className="gap-2"
            disabled={updateMutation.isPending}
            isLoading={updateMutation.isPending}
            loadingText="Saving..."
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            Save changes
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              if (!connection) {
                return;
              }
              setName(connection.name);
              setModel(connection.model);
              setDescription(connection.description ?? '');
              setConfigurationText(JSON.stringify(connection.configuration ?? {}, null, 2));
              setIsActive(connection.isActive);
              setApiKey('');
              setLocalError(null);
            }}
          >
            Reset
          </Button>
        </div>
      </form>
    </div>
  );
}
