'use client';

import { JSX } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';

import { Skeleton } from '@/components/ui/skeleton';
import { AgentDefinitionForm } from '../components/agent-definition-form';
import { fetchAgentDefinition } from '@/orchestration/agents';
import type { AgentDefinition } from '@/orchestration/agents';

interface PageProps {
  params: { agentId: string };
}

export default function EditAgentDefinitionPage({ params }: PageProps): JSX.Element {
  const router = useRouter();
  const { agentId } = params;

  const definitionQuery = useQuery<AgentDefinition>({
    queryKey: ['agent-definition', agentId],
    queryFn: () => fetchAgentDefinition(agentId),
  });

  if (definitionQuery.isLoading) {
    return (
      <div className="space-y-6">
        <div className="surface-panel rounded-3xl p-6 shadow-soft">
          <Skeleton className="h-6 w-48" />
        </div>
      </div>
    );
  }

  if (definitionQuery.isError || !definitionQuery.data) {
    return (
      <div className="surface-panel rounded-3xl p-6 shadow-soft text-[color:var(--text-secondary)]">
        <p className="text-sm">We couldn&apos;t load this agent definition.</p>
      </div>
    );
  }

  return (
    <AgentDefinitionForm
      mode="edit"
      agentId={agentId}
      initialAgent={definitionQuery.data}
      onComplete={() => router.push('/agents/definitions')}
    />
  );
}
