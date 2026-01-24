'use client';

import { JSX, useEffect, useState } from 'react';
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
  fetchConnector,
  updateConnector,
  type ConnectorResponse,
  type UpdateConnectorPayload,
} from '@/orchestration/connectors';

interface ConnectorUpdateProps {
  connectorId: string;
  organizationId: string;
}

const connectorQueryKey = (organizationId: string, connectorId: string) =>
  ['connector', organizationId, connectorId] as const;

function resolveError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

export function ConnectorUpdate({ connectorId, organizationId }: ConnectorUpdateProps): JSX.Element {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [configText, setConfigText] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const connectorQuery = useQuery({
    queryKey: connectorQueryKey(organizationId, connectorId),
    queryFn: () => fetchConnector(organizationId, connectorId),
    enabled: Boolean(organizationId && connectorId),
  });

  const connector = connectorQuery.data;

  useEffect(() => {
    if (!connector) {
      return;
    }
    setName(connector.name);
    setDescription(connector.description ?? '');
    setConfigText(JSON.stringify(connector.config ?? {}, null, 2));
  }, [connector]);

  const updateMutation = useMutation({
    mutationFn: (payload: UpdateConnectorPayload) =>
      updateConnector(organizationId, connectorId, payload),
    onSuccess: (updatedConnector: ConnectorResponse) => {
      queryClient.setQueryData(connectorQueryKey(organizationId, connectorId), updatedConnector);
      queryClient.invalidateQueries({ queryKey: ['connectors', organizationId] });
      toast({
        title: 'Connector saved',
        description: `"${updatedConnector.name}" has been updated.`,
      });
    },
    onError: (error: unknown) => {
      toast({
        title: 'Update failed',
        description: resolveError(error),
        variant: 'destructive',
      });
    },
  });

  const handleSubmit: React.FormEventHandler<HTMLFormElement> = (event) => {
    event.preventDefault();
    if (!organizationId) {
      setLocalError('Select an organization scope before saving changes.');
      return;
    }
    setLocalError(null);

    let parsedConfig: Record<string, unknown> | undefined;
    const trimmed = configText.trim();
    if (trimmed) {
      try {
        parsedConfig = JSON.parse(trimmed) as Record<string, unknown>;
      } catch {
        setLocalError('Connector configuration must be valid JSON.');
        return;
      }
    }

    const payload: UpdateConnectorPayload = {
      organizationId,
    };

    if (name.trim() && name.trim() !== connector?.name) {
      payload.name = name.trim();
    }
    payload.description = description.trim() || undefined;
    if (connector?.connectorType) {
      payload.connectorType = connector.connectorType;
    }
    if (connector?.projectId) {
      payload.projectId = connector.projectId;
    }
    if (parsedConfig) {
      payload.config = { config: parsedConfig };
    }

    updateMutation.mutate(payload);
  };

  if (connectorQuery.isLoading) {
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

  if (connectorQuery.isError || !connector) {
    return (
      <div className="space-y-4 text-sm text-[color:var(--text-muted)]">
        <p>We couldn&apos;t load that connector.</p>
        <Button variant="outline" size="sm" onClick={() => connectorQuery.refetch()}>
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
          onClick={() => router.push(`/datasources/${organizationId}`)}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to connections
        </Button>
        <h1 className="text-xl font-semibold text-[color:var(--text-primary)]">{connector.name}</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="connector-name">Name</Label>
            <Input
              id="connector-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Warehouse name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="connector-type">Connector type</Label>
            <Input id="connector-type" value={connector.connectorType ?? 'Unknown'} readOnly />
          </div>

          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="connector-description">Description</Label>
            <Textarea
              id="connector-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Short summary of this data source"
              rows={3}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="connector-config">Configuration (JSON)</Label>
          <Textarea
            id="connector-config"
            value={configText}
            onChange={(event) => setConfigText(event.target.value)}
            rows={12}
            className="font-mono text-xs"
          />
          <p className="text-xs text-[color:var(--text-muted)]">
            Update credentials or connection details. These values map directly to the connector runtime configuration.
          </p>
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
              setName(connector.name);
              setDescription(connector.description ?? '');
              setConfigText(JSON.stringify(connector.config ?? {}, null, 2));
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
