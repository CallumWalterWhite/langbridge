'use client';

import { JSX, useEffect } from 'react';
import { LLMConnectionUpdate } from '@/app/(app)/agents/llm/[connectionId]/_components/LLMConnectionUpdate';
import { useWorkspaceScope } from '@/context/workspaceScope';

type LLMConnectionPageProps = {
  params: { organizationId: string; connectionId: string };
};

export default function LLMConnectionPage({ params }: LLMConnectionPageProps): JSX.Element {
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (params.organizationId && params.organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(params.organizationId);
    }
  }, [params.organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  return <LLMConnectionUpdate organizationId={params.organizationId} connectionId={params.connectionId} />;
}
