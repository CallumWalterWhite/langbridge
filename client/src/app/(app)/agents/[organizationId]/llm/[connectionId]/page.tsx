'use client';

import { JSX, use, useEffect } from 'react';
import { LLMConnectionUpdate } from '@/app/(app)/agents/llm/[connectionId]/_components/LLMConnectionUpdate';
import { useWorkspaceScope } from '@/context/workspaceScope';

type LLMConnectionPageProps = {
  params: Promise<{ organizationId: string; connectionId: string }>;
};

export default function LLMConnectionPage({ params }: LLMConnectionPageProps): JSX.Element {
  const { organizationId, connectionId } = use(params);
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  return <LLMConnectionUpdate organizationId={organizationId} connectionId={connectionId} />;
}
