'use client';

import { JSX, use, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useWorkspaceScope } from '@/context/workspaceScope';

type LLMConnectionRedirectProps = {
  params: Promise<{ connectionId: string }>;
};

export default function LLMConnectionRedirect({ params }: LLMConnectionRedirectProps): JSX.Element {
  const { connectionId } = use(params);
  const router = useRouter();
  const { selectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (selectedOrganizationId) {
      router.replace(`/agents/${selectedOrganizationId}/llm/${connectionId}`);
    }
  }, [connectionId, router, selectedOrganizationId]);

  return (
    <div className="surface-panel rounded-3xl p-6 shadow-soft text-sm text-[color:var(--text-secondary)]">
      Select an organization to continue.
    </div>
  );
}
