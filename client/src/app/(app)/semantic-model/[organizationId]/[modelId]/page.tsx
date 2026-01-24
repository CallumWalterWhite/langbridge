'use client';

import { JSX, useEffect } from 'react';

import { useWorkspaceScope } from '@/context/workspaceScope';
import { SemanticModelDetail } from '../../[modelId]/_components/SemanticModelDetail';

type SemanticModelPageProps = {
  params: { modelId: string; organizationId: string };
};

export default function SemanticModelPage({ params }: SemanticModelPageProps): JSX.Element {
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  return <SemanticModelDetail modelId={params.modelId} organizationId={organizationId} />;
}
