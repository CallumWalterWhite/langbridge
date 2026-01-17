'use client';

import { JSX, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Copy, Download, Loader2, RefreshCw, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { useWorkspaceScope } from '@/context/workspaceScope';
import { ApiError } from '@/orchestration/http';
import {
  deleteSemanticModel,
  fetchSemanticModel,
  fetchSemanticModelYaml,
} from '@/orchestration/semanticModels';

import {
  type SemanticModelRecord
} from '@/orchestration/semanticModels/types';

interface SemanticModelDetailProps {
  modelId: string;
}

const semanticModelQueryKey = (organizationId: string | null | undefined, modelId: string) =>
  ['semantic-model', organizationId, modelId] as const;
const semanticModelYamlQueryKey = (organizationId: string | null | undefined, modelId: string) =>
  ['semantic-model-yaml', organizationId, modelId] as const;

function resolveError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

export function SemanticModelDetail({ modelId }: SemanticModelDetailProps): JSX.Element {
  const router = useRouter();
  const { toast } = useToast();
  const { selectedOrganizationId } = useWorkspaceScope();
  const queryClient = useQueryClient();

  const organizationId = selectedOrganizationId ?? '';
  const organizationSelected = Boolean(organizationId);

  const semanticModelQuery = useQuery<SemanticModelRecord>({
    queryKey: semanticModelQueryKey(organizationId, modelId),
    queryFn: () => fetchSemanticModel(modelId, organizationId),
    enabled: organizationSelected,
  });

  const yamlQuery = useQuery<string>({
    queryKey: semanticModelYamlQueryKey(organizationId, modelId),
    queryFn: () => fetchSemanticModelYaml(modelId, organizationId),
    enabled: organizationSelected,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteSemanticModel(modelId, organizationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['semantic-models'] });
      toast({
        title: 'Semantic model removed',
        description: 'The model has been deleted.',
      });
      router.push('/semantic-model');
    },
    onError: (error: unknown) => {
      toast({
        title: 'Unable to delete',
        description: resolveError(error),
        variant: 'destructive',
      });
    },
  });

  useEffect(() => {
    if (!organizationSelected) {
      toast({
        title: 'Select an organization',
        description: 'Choose a workspace scope to load semantic models.',
        variant: 'destructive',
      });
    }
  }, [organizationSelected, toast]);

  const semanticModel = semanticModelQuery.data;
  const yaml = yamlQuery.data ?? '';

  const formattedUpdatedAt = useMemo(() => {
    if (!semanticModel) {
      return null;
    }
    try {
      return new Date(semanticModel.updatedAt).toLocaleString();
    } catch {
      return null;
    }
  }, [semanticModel]);

  const handleDownload = async () => {
    if (!yaml) {
      return;
    }
    const blob = new Blob([yaml], { type: 'text/yaml;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${semanticModel?.name ?? 'semantic-model'}.yml`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    if (!yaml) {
      return;
    }
    try {
      await navigator.clipboard.writeText(yaml);
      toast({
        title: 'YAML copied',
        description: 'Semantic model YAML copied to clipboard.',
      });
    } catch {
      toast({
        title: 'Could not copy',
        description: 'Copy action failed. Try again from the builder.',
        variant: 'destructive',
      });
    }
  };

  if (!organizationSelected) {
    return (
      <div className="space-y-4 text-sm text-[color:var(--text-muted)]">
        <p>Select an organization to view this semantic model.</p>
        <Button variant="outline" size="sm" onClick={() => router.push('/semantic-model')}>
          Back to list
        </Button>
      </div>
    );
  }

  if (semanticModelQuery.isLoading || yamlQuery.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (semanticModelQuery.isError || yamlQuery.isError || !semanticModel) {
    return (
      <div className="space-y-4 text-sm text-[color:var(--text-muted)]">
        <p>We couldn&apos;t load that semantic model.</p>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => {
            semanticModelQuery.refetch();
            yamlQuery.refetch();
          }}>
            Try again
          </Button>
          <Button variant="ghost" size="sm" onClick={() => router.push('/semantic-model')}>
            Back to list
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-2 text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
          onClick={() => router.push('/semantic-model')}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to models
        </Button>
        <div>
          <h1 className="text-xl font-semibold text-[color:var(--text-primary)]">{semanticModel.name}</h1>
          {formattedUpdatedAt ? (
            <p className="text-xs text-[color:var(--text-muted)]">Updated {formattedUpdatedAt}</p>
          ) : null}
        </div>
      </div>

      <div className="space-y-2 text-sm">
        {semanticModel.description ? (
          <p className="text-[color:var(--text-secondary)]">{semanticModel.description}</p>
        ) : (
          <p className="text-[color:var(--text-muted)]">No description provided.</p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" size="sm" className="gap-2" onClick={handleDownload}>
          <Download className="h-4 w-4" aria-hidden="true" />
          Download YAML
        </Button>
        <Button type="button" variant="outline" size="sm" className="gap-2" onClick={handleCopy}>
          <Copy className="h-4 w-4" aria-hidden="true" />
          Copy YAML
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={() => router.push(`/semantic-model/create?modelId=${modelId}`)}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Edit in builder
        </Button>
        <Button
          type="button"
          variant="default"
          size="sm"
          className="gap-2"
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
        >
          {deleteMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          )}
          Delete
        </Button>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-[color:var(--text-primary)]" htmlFor="semantic-model-yaml">
          YAML definition
        </label>
        <Textarea
          id="semantic-model-yaml"
          value={yaml}
          readOnly
          rows={24}
          className="font-mono text-xs"
        />
        <p className="text-xs text-[color:var(--text-muted)]">
          Use the builder to update measures, dimensions, and relationships for this model.
        </p>
      </div>
    </div>
  );
}
